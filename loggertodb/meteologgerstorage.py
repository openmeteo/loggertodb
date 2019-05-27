import datetime as dt
import logging
import os
import re
import struct
from abc import ABC, abstractmethod
from glob import glob

import iso8601
import numpy as np
import pandas as pd
from pytz import timezone
from simpletail import ropen

from .exceptions import ConfigurationError, MeteologgerStorageReadError

pyodbc = None


class MeteologgerStorage(ABC):
    def __init__(self, parameters, logger=None):
        self.__check_parameters(parameters)
        self.station_id = int(parameters["station_id"])
        self.path = parameters["path"]
        self.timezone = timezone(parameters.get("timezone", "UTC"))
        self.logger = logger
        if not self.logger:
            self.logger = logging.getLogger("loggerstorage")
            self.logger.setLevel(logging.WARNING)
            self.logger.addHandler(logging.StreamHandler())

    def __check_parameters(self, parameters):
        # Check that all required parameters are present
        for parameter in self.get_required_parameters():
            if parameter not in parameters:
                raise ConfigurationError('Parameter "{}" is required'.format(parameter))

        # Check that all given parameters are valid
        all_parameters = self.get_required_parameters() | self.get_optional_parameters()
        for parameter in parameters:
            if parameter not in all_parameters:
                raise ConfigurationError('Unknown parameter "{}"'.format(parameter))

    @property
    @abstractmethod
    def timeseries_ids(self):
        pass

    def get_recent_data(self, ts_id, after_timestamp):
        cached_after_timestamp = getattr(
            self, "_cached_after_timestamp", dt.datetime(9999, 12, 31)
        )
        if after_timestamp < cached_after_timestamp:
            self._extract_data(after_timestamp=after_timestamp)
        from_timestamp = after_timestamp + dt.timedelta(seconds=1)
        self._check_monotonic(self._cached_data[ts_id].index)
        return self._cached_data[ts_id].loc[from_timestamp:]

    def _check_monotonic(self, index):
        if index.is_monotonic:
            return
        else:
            self._raise_monotonic_exception(index)

    def _raise_monotonic_exception(self, index):
        offending_date = self._locate_first_nonmonotonic_date(index)
        raise ValueError(
            "File is incorrectly ordered after " + offending_date.isoformat()
        )

    def _locate_first_nonmonotonic_date(self, index):
        prev = None
        for current in index:
            if prev is not None and prev > current:
                return prev
            prev = current

    def _extract_data(self, after_timestamp):
        """Extract the part of the storage that is after_timestamp.

        Reads the part of the storage that is after_timestamp and puts it in
        self._cached_data, a dictionary mapping time series ids to pandas dataframes
        with the data.

        Also sets self._cached_after_timestamp.
        """

        # Read part of storage later than after_timestamp
        self.logger.info(
            "Reading data storage newer than {}".format(after_timestamp.isoformat())
        )
        storage_tail = self._get_storage_tail(after_timestamp)
        self.logger.info("{} new lines".format(len(storage_tail)))
        if len(storage_tail) > 0:
            self.logger.info(
                "First new date: {}".format(storage_tail[0]["timestamp"].isoformat())
            )

        # Start with empty time series
        index = np.empty(len(storage_tail), dtype="datetime64[s]")
        data = {
            ts_id: np.empty((len(storage_tail), 2), dtype=object)
            for ts_id in self.timeseries_ids
        }

        # Iterate through the storage tail and fill in the time series
        try:
            for i, record in enumerate(storage_tail):
                for ts_id in self.timeseries_ids:
                    v, f = self._extract_value_and_flags(ts_id, record)
                    index[i] = np.datetime64(record["timestamp"])
                    data[ts_id][i, 0] = v
                    data[ts_id][i, 1] = f
        except ValueError as e:
            message = "parsing error while trying to read values: " + str(e)
            self._raise_error(record["line"], message)

        # Replace self._cached_data and self._after_timestamp, if any
        self._cached_data = {
            ts_id: pd.DataFrame(
                columns=["value", "flags"], index=index, data=data[ts_id]
            )
            for ts_id in self.timeseries_ids
        }
        self._cached_after_timestamp = after_timestamp

    @abstractmethod
    def _get_storage_tail(self, after_timestamp):
        """Read the part of the data storage after_timestamp.

        Returns a list of dictionaries. Each of these dictionaries is a measurement
        record (typically with many measurements).  The first item in the returned list
        is the first record that has a timestamp later than after_timestamp.

        Each dictionary has a "timestamp" key, a datetime object. The rest of the keys
        depend on the specific storage class. For TextFileMeteologgerStorage, there's
        one more key, "line", with a string with the entire line in the file. For wdat5,
        there are keys like "outsidetemp" etc., holding the values of the variables.
        """

    def _fix_dst(self, adatetime):
        """Remove any DST from a date.

           Determine if a date contains DST. If it does, remove the
           extra hour. Returns the fixed date.
        """
        result = adatetime
        if self.timezone.zone != "UTC":
            now = dt.datetime.now(self.timezone)
            now_naive = now.replace(tzinfo=None)
            is_dst = bool(now.dst()) and (
                abs(adatetime - now_naive) < dt.timedelta(hours=24)
            )
            result -= self.timezone.dst(adatetime, is_dst=is_dst)
        return result

    def _raise_error(self, line, msg):
        errmessage = '{}: "{}": {}'.format(self.path, line, msg)
        self.logger.error("Error while parsing, message: " + errmessage)
        raise MeteologgerStorageReadError(errmessage)

    def get_required_parameters(self):
        return {"path", "storage_format", "station_id"}

    def get_optional_parameters(self):
        return {"timezone"}

    @abstractmethod
    def _extract_value_and_flags(self, ts_id, record):
        pass


class TextFileMeteologgerStorage(MeteologgerStorage):
    def __init__(self, parameters, logger=None):
        super().__init__(parameters, logger=logger)
        self.fields = [int(x) for x in parameters.get("fields", "").split(",") if x]
        self.subset_identifiers = parameters.get("subset_identifiers", "")
        self.delimiter = parameters.get("delimiter", None)
        self.decimal_separator = parameters.get("decimal_separator", "")
        self.date_format = parameters.get("date_format", "")
        self.nullstr = parameters.get("nullstr", "")
        self.nfields_to_ignore = int(parameters.get("nfields_to_ignore", "0"))

    def get_required_parameters(self):
        return super().get_required_parameters() | {"fields"}

    def get_optional_parameters(self):
        return super().get_optional_parameters() | {"nullstr"}

    @property
    def timeseries_ids(self):
        return set(self.fields) - {0}

    def _subset_identifiers_match(self, line):
        return True

    @abstractmethod
    def _extract_timestamp(self, line):
        pass

    def _extract_value_and_flags(self, ts_id, record):
        for seq, tid in enumerate(self.fields, start=1):
            if tid == ts_id:
                break
        v, f = self._get_item_from_line(record["line"], seq)
        if self.decimal_separator and (self.decimal_separator != "."):
            v = v.replace(self.decimal_separator, ".")
        return v, f

    @abstractmethod
    def _get_item_from_line(self, line, seq):
        pass

    def _get_storage_tail(self, after_timestamp):
        result = []
        with ropen(self.path) as xr:
            prev_timestamp = ""
            for line in xr:
                self.logger.debug(line)

                # Omit empty or irrelevant lines
                if not line.strip() or not self._subset_identifiers_match(line):
                    continue

                timestamp = self._extract_timestamp(line).replace(second=0)
                timestamp = self._fix_dst(timestamp)
                if timestamp == prev_timestamp:
                    w = "Omitting line with repeated timestamp " + timestamp.isoformat()
                    self.logger.warning(w)
                    continue
                prev_timestamp = timestamp
                self.logger.debug("Timestamp: " + timestamp.isoformat())
                if timestamp <= after_timestamp:
                    break
                result.append({"timestamp": timestamp, "line": line})

        result.reverse()
        return result


class MeteologgerStorage_deltacom(TextFileMeteologgerStorage):
    deltacom_flags = {
        "#": "LOGOVERRUN",
        "$": "LOGNOISY",
        "%": "LOGOUTSIDE",
        "&": "LOGRANGE",
    }

    def _extract_timestamp(self, line):
        try:
            return iso8601.parse_date(line.split()[0], default_timezone=None)
        except (ValueError, iso8601.ParseError):
            self._raise_error(line, "parse error or invalid date")

    def _get_item_from_line(self, line, seq):
        flags = ""
        item = line.split()[seq].strip()
        if item[-1] in self.deltacom_flags.keys():
            flags = self.deltacom_flags[item[-1]]
            item = item[:-1]
        if self.nullstr and item == self.nullstr:
            item = "NaN"
        return (float(item), flags)


class MeteologgerStorage_pc208w(TextFileMeteologgerStorage):
    def get_required_parameters(self):
        return super().get_required_parameters() | {"subset_identifiers"}

    def _extract_timestamp(self, line):
        try:
            items = line.split(",")
            year = int(items[2])
            yday = int(items[3])
            hour = int(items[4]) // 100
            minute = int(items[4]) % 100
            if hour == 24:
                hour = 0
                yday = yday + 1
            return dt.datetime(year, 1, 1, hour, minute) + dt.timedelta(yday - 1)
        except (IndexError, ValueError):
            self._raise_error(line, "parse error or invalid date")

    def _get_item_from_line(self, line, seq):
        try:
            item = line.split(",")[seq + 4].strip()
        except IndexError:
            raise ValueError()
        if self.nullstr:
            if item == self.nullstr:
                item = float("NaN")
        return (float(item), "")

    def _subset_identifiers_match(self, line):
        si = line.split(",")[0].strip()
        return si == self.subset_identifiers


class MeteologgerStorage_CR1000(TextFileMeteologgerStorage):
    def get_required_parameters(self):
        return super().get_required_parameters() | {"subset_identifiers"}

    def _extract_timestamp(self, line):
        try:
            datestr = line.split(",")[0].strip('"')
            return iso8601.parse_date(datestr[:16], default_timezone=None)
        except (IndexError, iso8601.ParseError):
            self._raise_error(line, "parse error or invalid date")

    def _get_item_from_line(self, line, seq):
        item = line.split(",")[seq + 3].strip()
        if self.nullstr and item == self.nullstr:
            item = "NaN"
        return (float(item), "")

    def _subset_identifiers_match(self, line):
        si = line.split(",")[3].strip()
        return si == self.subset_identifiers


class MeteologgerStorage_simple(TextFileMeteologgerStorage):
    def get_optional_parameters(self):
        more_parms = {"nfields_to_ignore", "delimiter", "date_format"}
        return super().get_optional_parameters() | more_parms

    def _extract_timestamp(self, line):
        try:
            items = line.split(self.delimiter)
            datestr = items[self.nfields_to_ignore]
            datestr = datestr.strip().strip('"').strip()
            self._separate_time = False
            if len(datestr) <= 10:
                datestr += " " + items[self.nfields_to_ignore + 1].strip('"')
                self._separate_time = True
            if self.date_format:
                result = dt.datetime.strptime(datestr, self.date_format).replace(
                    second=0
                )
            else:
                result = iso8601.parse_date(datestr[:16], default_timezone=None)
            return result
        except ValueError as e:
            self._raise_error(
                line.strip(), "invalid date '{0}': {1}".format(datestr, str(e))
            )

    def _get_item_from_line(self, line, seq):
        index = self.nfields_to_ignore + seq + (1 if self._separate_time else 0)
        value = line.split(self.delimiter)[index].strip().strip('"').strip()
        if self.nullstr and value == self.nullstr:
            value = "NaN"
        return (float(value), "")


class MeteologgerStorage_lastem(TextFileMeteologgerStorage):
    def get_required_parameters(self):
        return super().get_required_parameters() | {"subset_identifiers"}

    def get_optional_parameters(self):
        more_parms = {"decimal_separator", "delimiter", "date_format"}
        return super().get_optional_parameters() | more_parms

    def _extract_timestamp(self, line):
        try:
            date = line.split(self.delimiter)[3]
            return dt.datetime.strptime(date, self.date_format)
        except (IndexError, ValueError):
            self._raise_error(line, "parse error or invalid date")

    def _get_item_from_line(self, line, seq):
        value = line.split(self.delimiter)[seq + 3]
        if self.nullstr and value == self.nullstr:
            value = "NaN"
        else:
            value = value.replace(self.decimal_separator, ".")
        return (float(value), "")

    def _subset_identifiers_match(self, line):
        si = [x.strip() for x in line.split(self.delimiter)[0:3]]
        si1 = [x.strip() for x in self.subset_identifiers.split(",")]
        return si == si1


class MeteologgerStorage_wdat5(MeteologgerStorage):
    wdat_record_format = [
        "<b dataType",
        "<b archiveInterval",
        "<b iconFlags",
        "<b moreFlags",
        "<h packedTime",
        "<h outsideTemp",
        "<h hiOutsideTemp",
        "<h lowOutsideTemp",
        "<h insideTemp",
        "<h barometer",
        "<h outsideHum",
        "<h insideHum",
        "<H rain",
        "<h hiRainRate",
        "<h windSpeed",
        "<h hiWindSpeed",
        "<b windDirection",
        "<b hiWindDirection",
        "<h numWindSamples",
        "<h solarRad",
        "<h hiSolarRad",
        "<B UV",
        "<B hiUV",
        "<b leafTemp1",
        "<b leafTemp2",
        "<b leafTemp3",
        "<b leafTemp4",
        "<h extraRad",
        "<h newSensors1",
        "<h newSensors2",
        "<h newSensors3",
        "<h newSensors4",
        "<h newSensors5",
        "<h newSensors6",
        "<b forecast",
        "<B ET",
        "<b soilTemp1",
        "<b soilTemp2",
        "<b soilTemp3",
        "<b soilTemp4",
        "<b soilTemp5",
        "<b soilTemp6",
        "<b soilMoisture1",
        "<b soilMoisture2",
        "<b soilMoisture3",
        "<b soilMoisture4",
        "<b soilMoisture5",
        "<b soilMoisture6",
        "<b leafWetness1",
        "<b leafWetness2",
        "<b leafWetness3",
        "<b leafWetness4",
        "<b extraTemp1",
        "<b extraTemp2",
        "<b extraTemp3",
        "<b extraTemp4",
        "<b extraTemp5",
        "<b extraTemp6",
        "<b extraTemp7",
        "<b extraHum1",
        "<b extraHum2",
        "<b extraHum3",
        "<b extraHum4",
        "<b extraHum5",
        "<b extraHum6",
        "<b extraHum7",
    ]
    variables_labels = [x.split()[1].lower() for x in wdat_record_format[5:]]

    def get_optional_parameters(self):
        return (
            super().get_optional_parameters()
            | set(self.variables_labels)
            | {
                "temperature_unit",
                "rain_unit",
                "wind_speed_unit",
                "pressure_unit",
                "matric_potential_unit",
            }
        )

    @property
    def timeseries_ids(self):
        return {self.variables[lab] for lab in self.variables if self.variables[lab]}

    def __init__(self, parameters, logger=None):
        super().__init__(parameters, logger)

        self.variables = {}
        for label in self.variables_labels:
            self.variables[label] = parameters.get(label)

        unit_parameters = {
            "temperature_unit": ("C", "F"),
            "rain_unit": ("mm", "inch"),
            "wind_speed_unit": ("m/s", "mph"),
            "pressure_unit": ("hPa", "inch Hg"),
            "matric_potential_unit": ("centibar", "cm"),
        }
        for p in unit_parameters:
            setattr(self, p, parameters.get(p, unit_parameters[p][0]))
            if self.__dict__[p] not in unit_parameters[p]:
                raise ConfigurationError(
                    "{} must be one of {}".format(p, ", ".join(unit_parameters[p]))
                )

    def _extract_timestamp(self):
        pass

    def _get_storage_tail(self, after_timestamp):
        """Read the part of the data storage after_timestamp.

        See the docstring of the inherited method for more information.
        """
        result = []
        saveddir = os.getcwd()
        try:
            os.chdir(self.path)
            first_file = "{0.year:04}-{0.month:02}.wlk".format(after_timestamp)
            filename_regexp = re.compile(r"\d{4}-\d{2}.wlk$")
            data_files = [
                x for x in glob("*.wlk") if filename_regexp.match(x) and x >= first_file
            ]
            data_files.sort()
            for current_file in data_files:
                result.extend(self._get_tail_part(after_timestamp, current_file))
        finally:
            os.chdir(saveddir)
        return result

    def _get_tail_part(self, after_timestamp, filename):
        """Read a single wdat5 file.

        Reads the single wdat5 file "filename" for records with
        date > after_timestamp, and returns a list of records in space-delimited
        format; iso datetime first, values after.
        """
        year, month = [
            int(x) for x in os.path.split(filename)[1].split(".")[0].split("-")
        ]
        result = []
        with open(filename, "rb") as f:
            header = f.read(212)
            if header[:6] != b"WDAT5.":
                raise MeteologgerStorageReadError(
                    "File {0} does not appear to be a WDAT 5.x file".format(filename)
                )
            for day in range(1, 32):
                i = 20 + (day * 6)
                j = i + 6
                day_index = header[i:j]
                records_in_day = struct.unpack("<h", day_index[:2])[0]
                start_pos = struct.unpack("<l", day_index[2:])[0]
                for r in range(records_in_day):
                    f.seek(212 + ((start_pos + r) * 88))
                    record = f.read(88)
                    if record[0] != b"\x01"[0]:
                        continue
                    decoded_record = self.__decode_wdat_record(record)
                    timestamp = dt.datetime(
                        year=year, month=month, day=day
                    ) + dt.timedelta(minutes=decoded_record["packedtime"])
                    timestamp = self._fix_dst(timestamp)
                    if timestamp <= after_timestamp:
                        continue
                    decoded_record["timestamp"] = timestamp
                    result.append(decoded_record)
        return result

    def __decode_wdat_record(self, record):
        """Decode bytes into a dictionary.
        """
        result = {}

        # Read raw values
        offset = 0
        for item in self.wdat_record_format:
            fmt, name = item.split()
            result[name.lower()] = struct.unpack_from(fmt, record, offset)[0]
            offset += struct.calcsize(fmt)

        # Convert temperature
        for x in ["outsidetemp", "hioutsidetemp", "lowoutsidetemp", "insidetemp"]:
            result[x] = (
                result[x] / 10.0
                if self.temperature_unit == "F"
                else ((result[x] / 10.0) - 32) * 5 / 9.0
            )

        # Convert pressure
        result["barometer"] = (
            result["barometer"] / 1000.0
            if self.pressure_unit == "inch Hg"
            else result["barometer"] / 1000.0 * 25.4 * 1.33322387415
        )

        # Convert humidity
        for x in ["outsidehum", "insidehum"]:
            result[x] = result[x] / 10.0

        # Convert rain
        rain_collector_type = result["rain"] & 0xF000
        rain_clicks = result["rain"] & 0x0FFF
        depth_per_click = {
            0x0000: 0.1 * 25.4,
            0x1000: 0.01 * 25.4,
            0x2000: 0.2,
            0x3000: 1.0,
            0x6000: 0.1,
        }[rain_collector_type]
        depth = depth_per_click * rain_clicks
        result["rain"] = depth / 25.4 if self.rain_unit == "inch" else depth
        rate = result["hirainrate"] * depth_per_click
        result["hirainrate"] = rate / 25.4 if self.rain_unit == "inch" else rate

        # Convert wind speed
        def convert_wind_speed(x):
            return (
                x / 10.0
                if self.wind_speed_unit == "mph"
                else x / 10.0 * 1609.344 / 3600
            )

        result["windspeed"] = convert_wind_speed(result["windspeed"])
        result["hiwindspeed"] = convert_wind_speed(result["hiwindspeed"])

        # Convert wind direction
        for x in ["winddirection", "hiwinddirection"]:
            result[x] = result[x] / 16.0 * 360 if result[x] >= 0 else "NaN"

        # Convert UV index
        result["uv"] = result["uv"] / 10.0
        result["hiuv"] = result["hiuv"] / 10.0

        # Convert evapotranspiration
        result["et"] = result["et"] / 1000.0
        if self.rain_unit == "inch":
            result["et"] *= 25.4

        # Convert matric potential
        for i in range(1, 7):
            varname = "soilmoisture" + str(i)
            result[varname] = (
                result[varname]
                if self.matric_potential_unit == "centibar"
                else result[varname] / 9.80638
            )

        # Convert extraTemp etc.
        extratemps = [
            "extratemp1",
            "extratemp2",
            "extratemp3",
            "extratemp4",
            "extratemp5",
            "extratemp6",
            "extratemp7",
            "soiltemp1",
            "soiltemp2",
            "soiltemp3",
            "soiltemp4",
            "soiltemp5",
            "soiltemp6",
            "leaftemp1",
            "leaftemp2",
            "leaftemp3",
            "leaftemp4",
        ]
        for x in extratemps:
            result[x] = (
                result[x] - 90
                if self.temperature_unit == "F"
                else ((result[x] - 90) - 32) * 5 / 9.0
            )

        return result

    def _extract_value_and_flags(self, ts_id, record):
        for v, tid in self.variables.items():
            if tid == ts_id:
                break
        return (record[v], "")


class MeteologgerStorage_odbc(MeteologgerStorage_simple):
    def get_required_parameters(self):
        return super().get_required_parameters() | {"table", "date_sql", "data_columns"}

    def get_optional_parameters(self):
        return super().get_optional_parameters() | {"date_format", "decimal_separator"}

    def __init__(self, parameters, logger=None):
        super().__init__(parameters, logger)
        self.table = parameters.get("table", "")
        self.date_sql = parameters.get("date_sql", "")
        self.data_columns = parameters.get("data_columns", "").split(",")
        self.delimiter = ";"

    def _get_storage_tail(self, after_timestamp):
        """Read the part of the data storage after_timestamp.

        See the docstring of the inherited method for more information.
        """
        try:
            # In the beginning of the file we have "pyodbc = None", so normally here
            # pyodbc will be imported. But if in the meantime some unit test has patched
            # pyodbc, no importing will be done.
            global pyodbc
            if pyodbc is None:
                import pyodbc
        except ImportError:
            self.logger.error("Install pyodbc to use odbc format")
            raise
        sql = """SELECT {} + ';' + {} FROM "{}" ORDER BY -id""".format(
            self.date_sql,
            " + ';' + ".join(['"{}"'.format(x) for x in self.data_columns]),
            self.table,
        )
        result = []
        connection = pyodbc.connect(self.path)
        cursor = connection.cursor()
        cursor.execute(sql)
        for row in cursor:  # Iterable cursor is a pyodbc feature
            line = row[0]  # Our SQL returns a single string
            self.logger.debug(line)
            date = self._extract_timestamp(line).replace(second=0)
            date = self._fix_dst(date)
            self.logger.debug("Date: " + date.isoformat())
            if date <= after_timestamp:
                break
            result.append({"timestamp": date, "line": line})
        result.reverse()
        return result
