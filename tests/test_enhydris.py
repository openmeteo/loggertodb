import datetime as dt
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from loggertodb.enhydris import Enhydris


@patch("loggertodb.enhydris.HTimeseries", new=lambda x: x)
class UploadTestCase(TestCase):
    @patch("loggertodb.enhydris.EnhydrisApiClient")
    def setUp(self, mock_EnhydrisApiClient):
        self.EnhydrisApiClient = mock_EnhydrisApiClient
        self._configure_EnhydrisApiClient(
            "get_ts_end_date.return_value", dt.datetime(2019, 3, 5, 7, 20)
        )
        self.MeteologgerStorage = MagicMock()
        self.enhydris = Enhydris(MagicMock())

    def _configure_EnhydrisApiClient(self, attribute, value):
        self.EnhydrisApiClient.configure_mock(**{f"return_value.{attribute}": value})

    def _configure_MeteologgerStorage(self, attribute, value):
        self.MeteologgerStorage.configure_mock(**{f"return_value.{attribute}": value})

    def test_calls_list_timeseries_as_needed(self):
        self._configure_MeteologgerStorage("station_id", 42)
        self._configure_MeteologgerStorage("timeseries_group_ids", {1, 2, 3})
        self._configure_EnhydrisApiClient("list_timeseries.return_value", [])
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
        self.enhydris.upload(self.MeteologgerStorage())
        self.EnhydrisApiClient.return_value.get_ts_end_date.assert_called_once_with(
            42, 1, 4242
        )

    def test_creates_timeseries_if_not_exists(self):
        self._configure_MeteologgerStorage("station_id", 42)
        self._configure_MeteologgerStorage("timeseries_group_ids", {1})
        self._configure_EnhydrisApiClient(
            "list_timeseries.return_value", [{"id": 4242, "type": "Checked"}]
        )
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
        self.enhydris.upload(self.MeteologgerStorage())
        self.EnhydrisApiClient.return_value.post_timeseries.assert_not_called()

    def test_uses_id_of_created_timeseries(self):
        self._configure_MeteologgerStorage("station_id", 42)
        self._configure_MeteologgerStorage("timeseries_group_ids", {1})
        self._configure_MeteologgerStorage("get_recent_data.return_value", "new data")
        self._configure_EnhydrisApiClient(
            "list_timeseries.return_value", [{"id": 4242, "type": "Checked"}]
        )
        self._configure_EnhydrisApiClient("post_timeseries.return_value", 9876)
        self.enhydris.upload(self.MeteologgerStorage())
        self.EnhydrisApiClient.return_value.post_tsdata.assert_has_calls(
            [call(42, 1, 9876, "new data")]
        )

    def test_calls_get_recent_data_as_needed(self):
        self._configure_MeteologgerStorage("timeseries_group_ids", {1, 2, 3})
        self._configure_MeteologgerStorage(
            "get_recent_data.side_effect", ["irrelevant", "irrelevant", "irrelevant"]
        )
        self.enhydris.upload(self.MeteologgerStorage())
        self.MeteologgerStorage.return_value.get_recent_data.assert_has_calls(
            [
                call(1, dt.datetime(2019, 3, 5, 7, 20)),
                call(2, dt.datetime(2019, 3, 5, 7, 20)),
                call(3, dt.datetime(2019, 3, 5, 7, 20)),
            ]
        )

    def test_calls_post_tsdata_as_needed(self):
        self._configure_MeteologgerStorage("station_id", 42)
        self._configure_MeteologgerStorage("timeseries_group_ids", {1, 2})
        self._configure_MeteologgerStorage(
            "get_recent_data.side_effect",
            [
                "new data for timeseries_group_id=1",
                "new data for timeseries_group_id=2",
            ],
        )
        self._configure_EnhydrisApiClient(
            "list_timeseries.side_effect",
            [[{"id": 4242, "type": "Initial"}], [{"id": 4243, "type": "Initial"}]],
        )
        self.enhydris.upload(self.MeteologgerStorage())
        self.EnhydrisApiClient.return_value.post_tsdata.assert_has_calls(
            [
                call(42, 1, 4242, "new data for timeseries_group_id=1"),
                call(42, 2, 4243, "new data for timeseries_group_id=2"),
            ]
        )
