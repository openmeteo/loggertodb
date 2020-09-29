import datetime as dt
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from loggertodb.enhydris import Enhydris


class UploadTestCase(TestCase):
    @patch("loggertodb.enhydris.EnhydrisApiClient")
    @patch("loggertodb.enhydris.HTimeseries", new=lambda x: x)
    def setUp(self, mock_EnhydrisApiClient):
        # Configure mock EnhydrisApiClient
        self.EnhydrisApiClient = mock_EnhydrisApiClient
        self.EnhydrisApiClient.configure_mock(
            **{
                "return_value.get_ts_end_date.return_value": dt.datetime(
                    2019, 3, 5, 7, 20
                )
            }
        )

        # Create a mock MeteologgerStorage
        self.MeteologgerStorage = MagicMock(
            **{
                "return_value.timeseries_ids": {1, 2, 3},
                "return_value.get_recent_data.side_effect": [
                    "new data for timeseries_id=1",
                    "new data for timeseries_id=2",
                    "new data for timeseries_id=3",
                ],
            }
        )

        self.enhydris = Enhydris(MagicMock())
        self.enhydris.upload(self.MeteologgerStorage())

    def test_called_get_recent_data_as_needed(self):
        self.MeteologgerStorage.return_value.get_recent_data.assert_has_calls(
            [
                call(1, dt.datetime(2019, 3, 5, 7, 20)),
                call(2, dt.datetime(2019, 3, 5, 7, 20)),
                call(3, dt.datetime(2019, 3, 5, 7, 20)),
            ]
        )

    def test_called_post_tsdata_as_needed(self):
        self.EnhydrisApiClient.post_tsdata.has_calls(
            [
                call(1, "new data for timeseries_id=1"),
                call(2, "new data for timeseries_id=2"),
                call(3, "new data for timeseries_id=3"),
            ]
        )
