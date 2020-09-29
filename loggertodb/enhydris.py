import datetime as dt

from enhydris_api_client import EnhydrisApiClient
from htimeseries import HTimeseries


class Enhydris:
    def __init__(self, configuration):
        self.base_url = configuration.base_url
        self.auth_token = configuration.auth_token
        self.client = EnhydrisApiClient(self.base_url, self.auth_token)

    def upload(self, meteologger_storage):
        self._meteologger_storage = meteologger_storage
        self._get_ts_end_dates()
        self._upload_all_new_data()

    def _get_ts_end_dates(self):
        station_id = self._meteologger_storage.station_id
        start_of_time = dt.datetime(1700, 1, 1)
        self._ts_end_dates = {
            ts_id: self.client.get_ts_end_date(station_id, ts_id) or start_of_time
            for ts_id in meteologger_storage.timeseries_ids
        }

    def _upload_all_new_data(self):
        station_id = self._meteologger_storage.station_id
        sorted_ts_end_dates = sorted(self._ts_end_dates.items(), key=lambda x: x[1])
        for ts_id, ts_end_date in sorted_ts_end_dates:
            new_data = self._meteologger_storage.get_recent_data(ts_id, ts_end_date)
            if len(new_data):
                self.client.post_tsdata(station_id, ts_id, HTimeseries(new_data))
