import datetime as dt
import textwrap
from unittest import TestCase

from pyfakefs.fake_filesystem_unittest import Patcher

from loggertodb import ConfigurationError
from loggertodb.meteologgerstorage import TextFileMeteologgerStorage


class DummyTextFileMeteologgerStorage(TextFileMeteologgerStorage):
    def _extract_timestamp(self, line):
        return dt.datetime.strptime(line[:16], "%Y-%m-%d %H:%M")

    def _get_item_from_line(self, line, seq):
        line_items = line.strip().split(",")[1:]
        item = line_items[seq - 1]
        item_items = item.split()
        return float(item_items[0]), " ".join(item_items[1:])


class CheckParametersTestCase(TestCase):
    def test_raises_error_on_fields_missing(self):
        expected_error_message = 'Parameter "fields" is required'
        with self.assertRaisesRegex(ConfigurationError, expected_error_message):
            DummyTextFileMeteologgerStorage(
                {"station_id": 1334, "path": "irrelevant", "storage_format": "dummy"}
            )

    def test_raises_error_on_invalid_parameter(self):
        expected_error_message = 'Unknown parameter "hello"'
        with self.assertRaisesRegex(ConfigurationError, expected_error_message):
            DummyTextFileMeteologgerStorage(
                {
                    "station_id": 1334,
                    "path": "irrelevant",
                    "storage_format": "dummy",
                    "fields": "5, 6",
                    "hello": "world",
                }
            )

    def test_accepts_allowed_optional_parameters(self):
        DummyTextFileMeteologgerStorage(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "dummy",
                "fields": "5, 6",
                "nullstr": "NULL",
            }
        )


class TimeseriesIdsTestCase(TestCase):
    def test_timeseries_ids(self):
        meteologger_storage = DummyTextFileMeteologgerStorage(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "dummy",
                "fields": "0, 5, 0, 6",
                "nullstr": "NULL",
            }
        )
        self.assertEqual(meteologger_storage.timeseries_ids, set((5, 6)))


class ExtractValueAndFlagsTestCase(TestCase):
    def setUp(self):
        self.meteologger_storage = DummyTextFileMeteologgerStorage(
            {
                "station_id": 1334,
                "path": "/foo/bar",
                "storage_format": "dummy",
                "fields": "5, 6",
                "nullstr": "NULL",
            }
        )
        self.record = {
            "timestamp": dt.datetime(2019, 2, 28, 17, 30),
            "line": "2019-02-28 17:30,42.2 MYFLAG1 MYFLAG2,24.3\n",
        }

    def test_value_with_flags(self):
        result = self.meteologger_storage._extract_value_and_flags(5, self.record)
        self.assertAlmostEqual(result[0], 42.2)
        self.assertEqual(result[1], "MYFLAG1 MYFLAG2")

    def test_value_without_flags(self):
        result = self.meteologger_storage._extract_value_and_flags(6, self.record)
        self.assertAlmostEqual(result[0], 24.3)
        self.assertEqual(result[1], "")


class GetStorageTailTestCase(TestCase):
    def setUp(self):
        meteologger_storage = DummyTextFileMeteologgerStorage(
            {
                "station_id": 1334,
                "path": "/foo/bar",
                "storage_format": "dummy",
                "fields": "5, 6",
                "nullstr": "NULL",
            }
        )
        with Patcher() as patcher:
            patcher.fs.create_file(
                "/foo/bar",
                contents=textwrap.dedent(
                    """\
                    2019-02-28 17:20,42.1,24.2
                    2019-02-28 17:30,42.2,24.3
                    2019-02-28 17:40,42.3,24.4
                    """
                ),
            )
            self.result = meteologger_storage._get_storage_tail(
                dt.datetime(2019, 2, 28, 17, 20)
            )

    def test_result(self):
        self.assertEqual(
            self.result,
            [
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 30),
                    "line": "2019-02-28 17:30,42.2,24.3\n",
                },
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 40),
                    "line": "2019-02-28 17:40,42.3,24.4\n",
                },
            ],
        )


class IgnoreLinesTestCase(TestCase):
    def setUp(self):
        meteologger_storage = DummyTextFileMeteologgerStorage(
            {
                "station_id": 1334,
                "path": "/foo/bar",
                "storage_format": "dummy",
                "fields": "5, 6",
                "nullstr": "NULL",
                "ignore_lines": "ignore( this)? line",
            }
        )
        with Patcher() as patcher:
            patcher.fs.create_file(
                "/foo/bar",
                contents=textwrap.dedent(
                    """\
                    ignore line
                    2019-02-28 17:20,42.1,24.2
                    ignore this line
                    2019-02-28 17:30,42.2,24.3
                    yes, really ignore line man!
                    2019-02-28 17:40,42.3,24.4
                    """
                ),
            )
            self.result = meteologger_storage._get_storage_tail(
                dt.datetime(2019, 2, 28, 17, 20)
            )

    def test_result(self):
        self.assertEqual(
            self.result,
            [
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 30),
                    "line": "2019-02-28 17:30,42.2,24.3\n",
                },
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 40),
                    "line": "2019-02-28 17:40,42.3,24.4\n",
                },
            ],
        )


class EncodingTestCase(TestCase):
    def setUp(self):
        meteologger_storage = DummyTextFileMeteologgerStorage(
            {
                "station_id": 1334,
                "path": "/foo/bar",
                "storage_format": "dummy",
                "fields": "5, 6",
                "nullstr": "NULL",
                "ignore_lines": "n' est pas",
                "encoding": "iso-8859-1",
            }
        )
        with Patcher() as patcher:
            patcher.fs.create_file(
                "/foo/bar",
                encoding="iso-8859-1",
                contents=textwrap.dedent(
                    """\
                    2019-02-28 17:20,42.1,24.2
                    Cette ligne n' est pas très importante
                    2019-02-28 17:30,42.2,24.3
                    2019-02-28 17:40,42.3,24.4
                    """
                ),
            )
            self.result = meteologger_storage._get_storage_tail(
                dt.datetime(2019, 2, 28, 17, 20)
            )

    def test_result(self):
        self.assertEqual(
            self.result,
            [
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 30),
                    "line": "2019-02-28 17:30,42.2,24.3\n",
                },
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 40),
                    "line": "2019-02-28 17:40,42.3,24.4\n",
                },
            ],
        )


class EncodingErrorsTestCase(TestCase):
    def setUp(self):
        # We use an iso-8859-1-encoded file but without declaring the encoding in the
        # parameters, so when it attempts to read it it will try utf8. It should forgive
        # the error
        meteologger_storage = DummyTextFileMeteologgerStorage(
            {
                "station_id": 1334,
                "path": "/foo/bar",
                "storage_format": "dummy",
                "fields": "5, 6",
                "nullstr": "NULL",
                "ignore_lines": "n' est pas",
            }
        )
        with Patcher() as patcher:
            patcher.fs.create_file(
                "/foo/bar",
                encoding="iso-8859-1",
                contents=textwrap.dedent(
                    """\
                    2019-02-28 17:20,42.1,24.2
                    Cette ligne n' est pas très importante
                    2019-02-28 17:30,42.2,24.3
                    2019-02-28 17:40,42.3,24.4
                    """
                ),
            )
            self.result = meteologger_storage._get_storage_tail(
                dt.datetime(2019, 2, 28, 17, 20)
            )

    def test_result(self):
        self.assertEqual(
            self.result,
            [
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 30),
                    "line": "2019-02-28 17:30,42.2,24.3\n",
                },
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 40),
                    "line": "2019-02-28 17:40,42.3,24.4\n",
                },
            ],
        )
