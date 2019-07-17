import datetime as dt
import textwrap

from pyfakefs.fake_filesystem_unittest import TestCase

from loggertodb.meteologgerstorage import MultiTextFileMeteologgerStorage


class DummyMultiTextFileMeteologgerStorage(MultiTextFileMeteologgerStorage):
    def _extract_timestamp(self, line):
        return dt.datetime.strptime(line[:16], "%Y-%m-%d %H:%M")

    def _get_item_from_line(self, line, seq):
        line_items = line.strip().split(",")[1:]
        item = line_items[seq - 1]
        item_items = item.split()
        return float(item_items[0]), " ".join(item_items[1:])


class GetStorageTailTestCase(TestCase):
    use_headers_in_files = False

    def setUp(self):
        self.setUpPyfakefs()
        self.meteologger_storage = self._get_meteologger_storage()
        self._create_files()

    def _get_meteologger_storage(self):
        parms = {
            "station_id": 1334,
            "path": "/foo/bar?",
            "storage_format": "dummy",
            "fields": "5, 6",
            "nullstr": "NULL",
        }
        if self.use_headers_in_files:
            parms["ignore_lines"] = "Date"
        return DummyMultiTextFileMeteologgerStorage(parms)

    def _create_files(self):
        self._create_test_file("/foo/bar1", 2018)
        self._create_test_file("/foo/bar2", 2019)
        self._create_test_file("/foo/bar3", 2017)

    def _create_test_file(self, pathname, year):
        headers = "Date,value1,value2\n" if self.use_headers_in_files else ""
        self.fs.create_file(
            pathname,
            contents=textwrap.dedent(
                """\
                {}
                {}-02-28 17:20,42.1,24.2
                {}-02-28 17:30,42.2,24.3
                """.format(
                    headers, year, year
                )
            ),
        )

    def test_get_storage_tail_from_last_file(self):
        self.result = self.meteologger_storage._get_storage_tail(
            dt.datetime(2019, 2, 28, 17, 20)
        )
        self.assertEqual(
            self.result,
            [
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 30),
                    "line": "2019-02-28 17:30,42.2,24.3\n",
                }
            ],
        )

    def test_get_storage_tail_from_last_but_one_file(self):
        self.result = self.meteologger_storage._get_storage_tail(
            dt.datetime(2018, 2, 28, 17, 20)
        )
        self.assertEqual(
            self.result,
            [
                {
                    "timestamp": dt.datetime(2018, 2, 28, 17, 30),
                    "line": "2018-02-28 17:30,42.2,24.3\n",
                },
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 20),
                    "line": "2019-02-28 17:20,42.1,24.2\n",
                },
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 30),
                    "line": "2019-02-28 17:30,42.2,24.3\n",
                },
            ],
        )

    def test_get_storage_tail_from_all_files(self):
        self.result = self.meteologger_storage._get_storage_tail(
            dt.datetime(2016, 2, 28, 17, 20)
        )
        self.assertEqual(
            self.result,
            [
                {
                    "timestamp": dt.datetime(2017, 2, 28, 17, 20),
                    "line": "2017-02-28 17:20,42.1,24.2\n",
                },
                {
                    "timestamp": dt.datetime(2017, 2, 28, 17, 30),
                    "line": "2017-02-28 17:30,42.2,24.3\n",
                },
                {
                    "timestamp": dt.datetime(2018, 2, 28, 17, 20),
                    "line": "2018-02-28 17:20,42.1,24.2\n",
                },
                {
                    "timestamp": dt.datetime(2018, 2, 28, 17, 30),
                    "line": "2018-02-28 17:30,42.2,24.3\n",
                },
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 20),
                    "line": "2019-02-28 17:20,42.1,24.2\n",
                },
                {
                    "timestamp": dt.datetime(2019, 2, 28, 17, 30),
                    "line": "2019-02-28 17:30,42.2,24.3\n",
                },
            ],
        )


class GetStorageTailNoFilesTestCase(TestCase):
    def setUp(self):
        self.meteologger_storage = self._get_meteologger_storage()

    def _get_meteologger_storage(self):
        return DummyMultiTextFileMeteologgerStorage(
            {
                "station_id": 1334,
                "path": "/foo/bar?",
                "storage_format": "dummy",
                "fields": "5, 6",
                "nullstr": "NULL",
            }
        )

    def test_get_storage_tail_returns_empty_list(self):
        result = self.meteologger_storage._get_storage_tail(
            dt.datetime(2016, 2, 28, 17, 20)
        )
        self.assertEqual(len(result), 0)


class GetStorageTailWithHeadersTestCase(GetStorageTailTestCase):
    use_headers_in_files = True


class GetStorageTailEmptyFileTestCase(TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.meteologger_storage = self._get_meteologger_storage()
        self._create_files()

    def _get_meteologger_storage(self):
        parms = {
            "station_id": 1334,
            "path": "/foo/bar?",
            "storage_format": "dummy",
            "fields": "5, 6",
            "nullstr": "NULL",
            "ignore_lines": "Date",
        }
        return DummyMultiTextFileMeteologgerStorage(parms)

    def _create_files(self):
        self._create_test_file("/foo/bar1", 2018)
        self._create_test_file("/foo/bar2", 2019)
        self._create_test_file("/foo/bar3", None)

    def _create_test_file(self, pathname, year):
        if year is None:
            self._create_empty_test_file(pathname)
        else:
            self._create_test_file_with_records(pathname, year)

    def _create_empty_test_file(self, pathname):
        self.fs.create_file(pathname, contents="Date,value1,value2\n")

    def _create_test_file_with_records(self, pathname, year):
        self.fs.create_file(
            pathname,
            contents=textwrap.dedent(
                """\
                Date,value1,value2
                {}-02-28 17:20,42.1,24.2
                {}-02-28 17:30,42.2,24.3
                """.format(
                    year, year
                )
            ),
        )

    def test_get_entire_storage_tail(self):
        self.result = self.meteologger_storage._get_storage_tail(
            dt.datetime(1700, 1, 1, 0, 0)
        )
        self.assertEqual(len(self.result), 4)


class BadFileOrder(TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.meteologger_storage = self._get_meteologger_storage()
        self._create_file()

    def _get_meteologger_storage(self):
        parms = {
            "station_id": 1334,
            "path": "/foo/bar?",
            "storage_format": "dummy",
            "fields": "5, 6",
            "nullstr": "NULL",
            "ignore_lines": "Date",
        }
        return DummyMultiTextFileMeteologgerStorage(parms)

    def _create_file(self):
        self.fs.create_file(
            "/foo/bar1",
            contents=textwrap.dedent(
                """\
                Date,value1,value2
                2019-02-28 17:20,42.1,24.2
                2018-02-28 17:30,42.2,24.3
                """
            ),
        )

    def test_raises_value_error(self):
        msg = "The order of timestamps in file /foo/bar1 is mixed up."
        with self.assertRaisesRegex(ValueError, msg):
            self.meteologger_storage.get_recent_data(5, dt.datetime(1700, 1, 1, 0, 0))


class FilesWithOverlap(TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.meteologger_storage = self._get_meteologger_storage()
        self._create_file1()
        self._create_file2()

    def _get_meteologger_storage(self):
        parms = {
            "station_id": 1334,
            "path": "/foo/bar?",
            "storage_format": "dummy",
            "fields": "5, 6",
            "nullstr": "NULL",
            "ignore_lines": "Date",
        }
        return DummyMultiTextFileMeteologgerStorage(parms)

    def _create_file1(self):
        self.fs.create_file(
            "/foo/bar1",
            contents=textwrap.dedent(
                """\
                Date,value1,value2
                2018-02-28 17:20,42.1,24.2
                2019-02-28 17:30,42.2,24.3
                """
            ),
        )

    def _create_file2(self):
        self.fs.create_file(
            "/foo/bar2",
            contents=textwrap.dedent(
                """\
                Date,value1,value2
                2019-02-28 17:20,42.1,24.2
                2020-02-28 17:30,42.2,24.3
                """
            ),
        )

    def test_raises_value_error(self):
        msg = "The timestamps in files /foo/bar1 and /foo/bar2 overlap."
        with self.assertRaisesRegex(ValueError, msg):
            self.meteologger_storage.get_recent_data(5, dt.datetime(1700, 1, 1, 0, 0))
