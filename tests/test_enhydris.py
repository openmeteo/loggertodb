import datetime as dt
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

import pandas as pd

from loggertodb.enhydris import Enhydris


@patch("loggertodb.enhydris.HTimeseries", new=lambda x: x)
class UploadTestCase(TestCase):
    @patch("loggertodb.enhydris.EnhydrisApiClient")
    def setUp(self, mock_EnhydrisApiClient):
        self.EnhydrisApiClient = mock_EnhydrisApiClient
        self.MeteologgerStorage = MagicMock()
        self.enhydris = Enhydris(MagicMock(), MagicMock())

    def _configure_EnhydrisApiClient(self, attribute, value):
        self.EnhydrisApiClient.configure_mock(**{f"return_value.{attribute}": value})

    def _configure_MeteologgerStorage(self, attribute, value):
        self.MeteologgerStorage.configure_mock(**{f"return_value.{attribute}": value})

    def _setup_get_ts_end_date(self):
        self._configure_EnhydrisApiClient(
            "get_ts_end_date.return_value", dt.datetime(2019, 3, 5, 7, 20)
        )

    def test_calls_list_timeseries_as_needed(self):
        self._configure_MeteologgerStorage("station_id", 42)
        self._configure_MeteologgerStorage("timeseries_group_ids", {1, 2, 3})
        self._configure_EnhydrisApiClient("list_timeseries.return_value", [])
        self._setup_get_ts_end_date()
        self.enhydris.upload(self.MeteologgerStorage())
        self.EnhydrisApiClient.return_value.list_timeseries.assert_has_calls(
            [call(42, 1), call(42, 2), call(42, 3)]
        )

    def test_determines_correct_timeseries_from_timeseries_group(self):
        self._configure_MeteologgerStorage("station_id", 42)
        self._configure_MeteologgerStorage("timeseries_group_ids", {1})
        self._configure_EnhydrisApiClient(
            "list_timeseries.return_value",
            [{"id": 4242, "type": "Initial"}, {"id": 4243, "type": "Checked"}],
        )
        self._setup_get_ts_end_date()
        self.enhydris.upload(self.MeteologgerStorage())
        self.EnhydrisApiClient.return_value.get_ts_end_date.assert_called_once_with(
            42, 1, 4242, timezone="Etc/GMT"
        )

    def test_creates_timeseries_if_not_exists(self):
        self._configure_MeteologgerStorage("station_id", 42)
        self._configure_MeteologgerStorage("timeseries_group_ids", {1})
        self._configure_EnhydrisApiClient(
            "list_timeseries.return_value", [{"id": 4242, "type": "Checked"}]
        )
        self._setup_get_ts_end_date()
        self.enhydris.upload(self.MeteologgerStorage())
        self.EnhydrisApiClient.return_value.post_timeseries.assert_called_once_with(
            42, 1, data={"type": "Initial", "time_step": "", "timeseries_group": 1}
        )

    def test_does_not_create_timeseries_if_exists(self):
        self._configure_MeteologgerStorage("station_id", 42)
        self._configure_MeteologgerStorage("timeseries_group_ids", {1})
        self._configure_EnhydrisApiClient(
            "list_timeseries.return_value", [{"id": 4242, "type": "Initial"}]
        )
        self._setup_get_ts_end_date()
        self.enhydris.upload(self.MeteologgerStorage())
        self.EnhydrisApiClient.return_value.post_timeseries.assert_not_called()

    def test_uses_id_of_created_timeseries(self):
        self._configure_MeteologgerStorage("station_id", 42)
        self._configure_MeteologgerStorage("timeseries_group_ids", {1})
        mock1 = MagicMock()
        mock1.__len__.return_value = 5
        self._configure_MeteologgerStorage("get_recent_data.return_value", mock1)
        self._configure_EnhydrisApiClient(
            "list_timeseries.return_value", [{"id": 4242, "type": "Checked"}]
        )
        self._configure_EnhydrisApiClient("post_timeseries.return_value", 9876)
        self._setup_get_ts_end_date()
        self.enhydris.upload(self.MeteologgerStorage())
        mock_calls = self.EnhydrisApiClient.return_value.post_tsdata.mock_calls
        self.assertEqual(mock_calls[0].args[:3], (42, 1, 9876))

    def test_calls_get_recent_data_as_needed(self):
        self._configure_MeteologgerStorage("timeseries_group_ids", {1, 2, 3})
        self._configure_MeteologgerStorage(
            "get_recent_data.side_effect", [MagicMock(), MagicMock(), MagicMock()]
        )
        self._setup_get_ts_end_date()
        self.enhydris.upload(self.MeteologgerStorage())
        self.MeteologgerStorage.return_value.get_recent_data.assert_has_calls(
            [
                call(1, dt.datetime(2019, 3, 5, 7, 20, tzinfo=dt.timezone.utc)),
                call(2, dt.datetime(2019, 3, 5, 7, 20, tzinfo=dt.timezone.utc)),
                call(3, dt.datetime(2019, 3, 5, 7, 20, tzinfo=dt.timezone.utc)),
            ]
        )

    def test_calls_get_recent_data_properly_when_timeseries_is_empty(self):
        self._configure_EnhydrisApiClient("get_ts_end_date.return_value", None)
        self._configure_MeteologgerStorage("timeseries_group_ids", {1, 2, 3})
        self._configure_MeteologgerStorage(
            "get_recent_data.side_effect", [MagicMock(), MagicMock(), MagicMock()]
        )
        self.enhydris.upload(self.MeteologgerStorage())
        self.MeteologgerStorage.return_value.get_recent_data.assert_has_calls(
            [
                call(1, dt.datetime(1700, 1, 1, tzinfo=dt.timezone.utc)),
                call(2, dt.datetime(1700, 1, 1, tzinfo=dt.timezone.utc)),
                call(3, dt.datetime(1700, 1, 1, tzinfo=dt.timezone.utc)),
            ]
        )

    def test_calls_post_tsdata_as_needed(self):
        self._configure_MeteologgerStorage("station_id", 42)
        self._configure_MeteologgerStorage("timeseries_group_ids", {1, 2})
        mock1, mock2 = MagicMock(), MagicMock()
        mock1.__len__.return_value = mock2.__len__.return_value = 5
        self._configure_MeteologgerStorage(
            "get_recent_data.side_effect", [mock1, mock2]
        )
        self._configure_EnhydrisApiClient(
            "list_timeseries.side_effect",
            [[{"id": 4242, "type": "Initial"}], [{"id": 4243, "type": "Initial"}]],
        )
        self._setup_get_ts_end_date()
        self.enhydris.upload(self.MeteologgerStorage())
        mock_calls = self.EnhydrisApiClient.return_value.post_tsdata.mock_calls
        self.assertEqual(len(mock_calls), 2)
        self.assertEqual(mock_calls[0].args[:3], (42, 1, 4242))
        self.assertEqual(mock_calls[1].args[:3], (42, 2, 4243))


class MaxRecordsTestCase(TestCase):
    @patch("loggertodb.enhydris.EnhydrisApiClient")
    def setUp(self, mock_EnhydrisApiClient):
        self.EnhydrisApiClient = mock_EnhydrisApiClient
        self.MeteologgerStorage = MagicMock()
        self.enhydris = Enhydris(MagicMock(), MagicMock())

    def _configure_MeteologgerStorage(self, attribute, value):
        self.MeteologgerStorage.configure_mock(**{f"return_value.{attribute}": value})

    def _configure_EnhydrisApiClient(self, attribute, value):
        self.EnhydrisApiClient.configure_mock(**{f"return_value.{attribute}": value})

    def _setup_get_ts_end_date(self):
        self._configure_EnhydrisApiClient(
            "get_ts_end_date.return_value", dt.datetime(2019, 3, 5, 7, 20)
        )

    def test_respects_max_records(self):
        self._configure_MeteologgerStorage("station_id", 42)
        self._configure_MeteologgerStorage("timeseries_group_ids", {1})

        df = pd.DataFrame(
            {"value": [10, 20, 30]},
            pd.date_range("2022-01-01", periods=3, freq="D"),
        )
        self._configure_MeteologgerStorage("get_recent_data.side_effect", [df])

        self._configure_EnhydrisApiClient(
            "list_timeseries.side_effect", [[{"id": 4242, "type": "Initial"}]]
        )
        self._setup_get_ts_end_date()
        self.enhydris.max_records = 2
        self.enhydris.upload(self.MeteologgerStorage())
        args, kwargs = self.EnhydrisApiClient.return_value.post_tsdata.call_args
        ahtimeseries = args[3]
        self.assertEqual(len(ahtimeseries.data), 2)
