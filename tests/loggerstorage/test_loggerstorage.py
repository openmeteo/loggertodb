import datetime as dt
from collections import OrderedDict
from unittest import TestCase
from unittest.mock import patch

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import pandas as pd

from loggertodb import ConfigurationError
from loggertodb.meteologgerstorage import MeteologgerStorage


class DummyMeteologgerStorage(MeteologgerStorage):
    def _get_storage_tail(self, after_timestamp):
        return [
            {"timestamp": after_timestamp + dt.timedelta(minutes=1), "line": "line1"},
            {"timestamp": after_timestamp + dt.timedelta(minutes=2), "line": "line2"},
        ]

    def _extract_value_and_flags(self, ts_id, record):
        # Use the ts_id as value and the whole line as flags
        return (ts_id, record["line"])

    @property
    def timeseries_group_ids(self):
        return (15, 16)


class DummyWrongOrderMeteologgerStorage(DummyMeteologgerStorage):
    """A file with a storage tail that contains records in the wrong order."""

    def _get_storage_tail(self, after_timestamp):
        result = super()._get_storage_tail(after_timestamp)
        result.reverse()
        return result


class MeteologgerStorageCheckParametersTestCase(TestCase):
    def test_raises_error_on_path_missing(self):
        expected_error_message = 'Parameter "path" is required'
        with self.assertRaisesRegex(ConfigurationError, expected_error_message):
            DummyMeteologgerStorage(
                {"station_id": 1334, "storage_format": "dummy", "timezone": "Etc/GMT-2"}
            )

    def test_raises_error_on_storage_format_missing(self):
        expected_error_message = 'Parameter "storage_format" is required'
        with self.assertRaisesRegex(ConfigurationError, expected_error_message):
            DummyMeteologgerStorage(
                {
                    "station_id": 1334,
                    "path": "irrelevant",
                    "timezone": "Etc/GMT-2",
                }
            )

    def test_raises_error_on_station_missing(self):
        expected_error_message = 'Parameter "station_id" is required'
        with self.assertRaisesRegex(ConfigurationError, expected_error_message):
            DummyMeteologgerStorage(
                {
                    "path": "irrelevant",
                    "storage_format": "dummy",
                    "timezone": "Etc/GMT-2",
                }
            )

    def test_raises_error_on_invalid_parameter(self):
        expected_error_message = 'Unknown parameter "hello"'
        with self.assertRaisesRegex(ConfigurationError, expected_error_message):
            DummyMeteologgerStorage(
                {
                    "station_id": 1334,
                    "path": "irrelevant",
                    "storage_format": "dummy",
                    "hello": "world",
                    "timezone": "Etc/GMT-2",
                }
            )


class MeteologgerStorageGetRecentDataTestCase(TestCase):
    def setUp(self):
        self.storage = DummyMeteologgerStorage(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "dummy",
                "timezone": "Etc/GMT-2",
            }
        )
        self.result = self.storage.get_recent_data(
            15, dt.datetime(2019, 2, 27, 12, 52, tzinfo=ZoneInfo("Etc/GMT-2"))
        )

    def test_return_value(self):
        expected_result = pd.DataFrame(
            data=OrderedDict([("value", [15, 15]), ("flags", ["line1", "line2"])]),
            index=[
                dt.datetime(2019, 2, 27, 10, 53, tzinfo=dt.timezone.utc),
                dt.datetime(2019, 2, 27, 10, 54, tzinfo=dt.timezone.utc),
            ],
            dtype=object,
        )
        pd.testing.assert_frame_equal(self.result, expected_result)

    def test_cached_return_value(self):
        # We have already called get_recent_data(). Now we call it again, for another
        # timeseries, and a timestamp later than the previous one. It should work
        # correctly.
        second_result = self.storage.get_recent_data(
            16, dt.datetime(2019, 2, 27, 12, 53, tzinfo=ZoneInfo("Etc/GMT-2"))
        )
        expected_result = pd.DataFrame(
            data=OrderedDict([("value", [16]), ("flags", ["line2"])]),
            index=[dt.datetime(2019, 2, 27, 10, 54, tzinfo=dt.timezone.utc)],
            dtype=object,
        )
        pd.testing.assert_frame_equal(second_result, expected_result)


class MeteologgerStorageGetRecentDataWrongOrderTestCase(TestCase):
    def setUp(self):
        self.storage = DummyWrongOrderMeteologgerStorage(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "dummy",
                "timezone": "Etc/GMT-2",
            }
        )

    def test_exception(self):
        msg = "incorrectly ordered after 2019-02-27 10:54:00 UTC"
        with self.assertRaisesRegex(ValueError, msg):
            self.result = self.storage.get_recent_data(
                15, dt.datetime(2019, 2, 27, 12, 52, tzinfo=ZoneInfo("Etc/GMT-2"))
            )


class PatchableDatetime(dt.datetime):
    """Patchable version of dt.datetime.

    mock.patch() can't patch dt.datetime.now(), because dt.datetime is written in C. We
    therefore create this subclass. Whenever we need to patch dt.datetime.now(), we
    first patch dt.datetime with this subclass, and then we can patch dt.datetime.now().
    """

    pass


class MeteologgerStorageFixDstTestCase(TestCase):
    def setUp(self):
        self.storage = DummyMeteologgerStorage(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "dummy",
                "timezone": "Europe/Athens",
            }
        )

    def test_date_without_dst(self):
        self.assertEqual(
            self.storage._get_datetime_with_correct_fold(
                dt.datetime(2019, 2, 27, 13, 39, tzinfo=ZoneInfo("Europe/Athens"))
            ),
            dt.datetime(2019, 2, 27, 11, 39, tzinfo=dt.timezone.utc),
        )

    def test_date_with_dst(self):
        self.assertEqual(
            self.storage._get_datetime_with_correct_fold(
                dt.datetime(2019, 4, 27, 13, 39, tzinfo=ZoneInfo("Europe/Athens"))
            ),
            dt.datetime(2019, 4, 27, 10, 39, tzinfo=dt.timezone.utc),
        )

    @patch(
        "loggertodb.meteologgerstorage.dt.datetime.now",
        return_value=dt.datetime(2018, 10, 28, 2, 0, tzinfo=dt.timezone.utc),
    )
    @patch("loggertodb.meteologgerstorage.dt.datetime", new=PatchableDatetime)
    def test_ambiguous_date_after_dst_switch(self, m):
        self.assertEqual(
            self.storage._get_datetime_with_correct_fold(
                dt.datetime(2018, 10, 28, 3, 30, tzinfo=ZoneInfo("Europe/Athens"))
            ).astimezone(dt.timezone.utc),
            dt.datetime(2018, 10, 28, 1, 30, tzinfo=dt.timezone.utc),
        )

    @patch(
        "loggertodb.meteologgerstorage.dt.datetime.now",
        return_value=dt.datetime(2018, 10, 28, 0, 0, tzinfo=dt.timezone.utc),
    )
    @patch("loggertodb.meteologgerstorage.dt.datetime", new=PatchableDatetime)
    def test_ambiguous_date_before_dst_switch(self, m):
        # See it once
        self.storage._get_datetime_with_correct_fold(
            dt.datetime(2018, 10, 28, 3, 30, tzinfo=ZoneInfo("Europe/Athens"))
        )

        # Then see it again
        self.assertEqual(
            self.storage._get_datetime_with_correct_fold(
                dt.datetime(2018, 10, 28, 3, 30, tzinfo=ZoneInfo("Europe/Athens"))
            ).astimezone(dt.timezone.utc),
            dt.datetime(2018, 10, 28, 0, 30, tzinfo=dt.timezone.utc),
        )
