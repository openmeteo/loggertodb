import datetime as dt
from collections import namedtuple

from enhydris_api_client import EnhydrisApiClient
from htimeseries import HTimeseries

CompositeTimeseriesId = namedtuple(
    "CompositeTimeseriesId", ("timeseries_group_id", "timeseries_id")
)


class Enhydris:
    def __init__(self, configuration):
        self.base_url = configuration.base_url
        self.auth_token = configuration.auth_token
        self.client = EnhydrisApiClient(self.base_url, self.auth_token)

    def upload(self, meteologger_storage):
        self._meteologger_storage = meteologger_storage
        self._get_composite_timeseries_ids()
        self._get_ts_end_dates()
        self._upload_all_new_data()

    def _get_composite_timeseries_ids(self):
        """Create a list of (timeseries_group_id, initial_timeseries_id) pairs."""
        station_id = self._meteologger_storage.station_id
        self._composite_timeseries_ids = []
        for timeseries_group_id in self._meteologger_storage.timeseries_group_ids:
            timeseries_id = self._get_timeseries_id(station_id, timeseries_group_id)
            self._composite_timeseries_ids.append(
                CompositeTimeseriesId(timeseries_group_id, timeseries_id)
            )

    def _get_timeseries_id(self, station_id, timeseries_group_id):
        timeseries = self.client.list_timeseries(station_id, timeseries_group_id)
        for item in timeseries:
            if item["type"] == "Initial":
                return item["id"]
        return self._create_timeseries(station_id, timeseries_group_id)

    def _create_timeseries(self, station_id, timeseries_group_id):
        return self.client.post_timeseries(
            station_id,
            timeseries_group_id,
            data={
                "type": "Initial",
                "time_step": "",
                "timeseries_group": timeseries_group_id,
            },
        )

    def _get_ts_end_dates(self):
        station_id = self._meteologger_storage.station_id
        start_of_time = dt.datetime(1700, 1, 1)
        self._ts_end_dates = {
            cts_id: self.client.get_ts_end_date(station_id, *cts_id) or start_of_time
            for cts_id in self._composite_timeseries_ids
        }

    def _upload_all_new_data(self):
        station_id = self._meteologger_storage.station_id
        sorted_ts_end_dates = sorted(self._ts_end_dates.items(), key=lambda x: x[1])
        for cts_id, ts_end_date in sorted_ts_end_dates:
            new_data = self._meteologger_storage.get_recent_data(
                cts_id.timeseries_group_id, ts_end_date
            )
            if len(new_data):
                self.client.post_tsdata(station_id, *cts_id, HTimeseries(new_data))
