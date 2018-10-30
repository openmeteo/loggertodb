import datetime as dt
import os
from unittest import TestCase
from unittest.mock import call, patch

from loggertodb.exceptions import ConfigurationError
from loggertodb.meteologgerstorage import MeteologgerStorage_wdat5


class ConfigurationTestCase(TestCase):
    def test_accepts_allowed_optional_parameters(self):
        MeteologgerStorage_wdat5(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "simple",
                "outsidetemp": 1256,
                "hioutsidetemp": 1257,
                "rain": 1652,
            }
        )

    def test_timeseries_ids(self):
        meteologger_storage = MeteologgerStorage_wdat5(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "wdat5",
                "outsidetemp": 1256,
                "hioutsidetemp": 1257,
                "rain": 1652,
            }
        )
        self.assertEqual(meteologger_storage.timeseries_ids, {1256, 1257, 1652})

    def test_valid_temperature_unit(self):
        MeteologgerStorage_wdat5(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "simple",
                "temperature_unit": "C",
            }
        )

    def test_invalid_temperature_unit(self):
        msg = "temperature_unit must be one of C, F"
        with self.assertRaisesRegex(ConfigurationError, msg):
            MeteologgerStorage_wdat5(
                {
                    "station_id": 1334,
                    "path": "irrelevant",
                    "storage_format": "simple",
                    "temperature_unit": "A",
                }
            )

    def test_valid_rain_unit(self):
        MeteologgerStorage_wdat5(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "simple",
                "rain_unit": "mm",
            }
        )

    def test_invalid_rain_unit(self):
        msg = "rain_unit must be one of mm, inch"
        with self.assertRaisesRegex(ConfigurationError, msg):
            MeteologgerStorage_wdat5(
                {
                    "station_id": 1334,
                    "path": "irrelevant",
                    "storage_format": "simple",
                    "rain_unit": "A",
                }
            )

    def test_valid_wind_speed_unit(self):
        MeteologgerStorage_wdat5(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "simple",
                "wind_speed_unit": "m/s",
            }
        )

    def test_invalid_wind_speed_unit(self):
        msg = "wind_speed_unit must be one of m/s, mph"
        with self.assertRaisesRegex(ConfigurationError, msg):
            MeteologgerStorage_wdat5(
                {
                    "station_id": 1334,
                    "path": "irrelevant",
                    "storage_format": "simple",
                    "wind_speed_unit": "A",
                }
            )

    def test_valid_pressure_unit(self):
        MeteologgerStorage_wdat5(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "simple",
                "pressure_unit": "hPa",
            }
        )

    def test_invalid_pressure_unit(self):
        msg = "pressure_unit must be one of hPa, inch Hg"
        with self.assertRaisesRegex(ConfigurationError, msg):
            MeteologgerStorage_wdat5(
                {
                    "station_id": 1334,
                    "path": "irrelevant",
                    "storage_format": "simple",
                    "pressure_unit": "A",
                }
            )

    def test_valid_matric_potential_unit(self):
        MeteologgerStorage_wdat5(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "simple",
                "matric_potential_unit": "centibar",
            }
        )

    def test_invalid_matric_potential_unit(self):
        msg = "matric_potential_unit must be one of centibar, cm"
        with self.assertRaisesRegex(ConfigurationError, msg):
            MeteologgerStorage_wdat5(
                {
                    "station_id": 1334,
                    "path": "irrelevant",
                    "storage_format": "simple",
                    "matric_potential_unit": "A",
                }
            )


class GetStorageTailTestCase(TestCase):
    @classmethod
    @patch(
        "loggertodb.meteologgerstorage.MeteologgerStorage._fix_dst",
        side_effect=lambda x: x,
    )
    def setUpClass(cls, m):
        cls.patched_fix_dst = m
        directory_of_this_file = os.path.dirname(os.path.abspath(__file__))
        meteologger_storage = MeteologgerStorage_wdat5(
            {
                "station_id": 1334,
                "path": os.path.join(directory_of_this_file, "wdat5_data"),
                "storage_format": "wdat5",
                "outsidetemp": 1256,
                "hioutsidetemp": 1257,
                "rain": 1652,
            }
        )
        cls.result = meteologger_storage._get_storage_tail(
            dt.datetime(2013, 12, 24, 22, 30)
        )

    def test_length(self):
        # The January 2014 file goes as far as 2014-01-03 12:10. Therefore we have 9
        # whole days (from 25 Dec to 2 Jan) or 9*144 = 1296 ten-minute intervals.
        # Plus 8 intervals from 2013-12-24 22:40 to 2013-12-24 23:50, plus 74 intervals
        # from 2014-01-03 00:00 to 12:10. Total 1378.
        self.assertEqual(len(self.result), 1378)

    def test_first_timestamp(self):
        self.assertEqual(self.result[0]["timestamp"], dt.datetime(2013, 12, 24, 22, 40))

    def test_last_timestamp(self):
        self.assertEqual(self.result[-1]["timestamp"], dt.datetime(2014, 1, 3, 12, 10))

    def test_first_outside_temp(self):
        self.assertAlmostEqual(self.result[0]["outsidetemp"], 8.7, places=1)

    def test_last_outside_temp(self):
        self.assertAlmostEqual(self.result[-1]["outsidetemp"], 13.6, places=1)

    def test_first_hum(self):
        self.assertEqual(self.result[0]["outsidehum"], 88)

    def test_last_hum(self):
        self.assertEqual(self.result[-1]["outsidehum"], 72)

    def test_fix_dst_was_called_enough_times(self):
        # ._fix_dst should have been called once for each December timestamp (31*144)
        # plus two whole days in January (2*144) plus 73 intervals from 2014-01-03 00:10
        # to 2014-01-03 12:10, total 4825.
        self.assertEqual(len(self.patched_fix_dst.mock_calls), 4825)

    def test_fix_dst_was_called_starting_with_first_date(self):
        self.assertEqual(
            self.patched_fix_dst.mock_calls[0], call(dt.datetime(2013, 12, 1, 0, 10))
        )

    def test_fix_dst_was_called_ending_with_last_date(self):
        self.assertEqual(
            self.patched_fix_dst.mock_calls[-1], call(dt.datetime(2014, 1, 3, 12, 10))
        )
