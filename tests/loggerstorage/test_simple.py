import datetime as dt
import logging
import math
from unittest import TestCase

from loggertodb.exceptions import MeteologgerStorageReadError
from loggertodb.meteologgerstorage import MeteologgerStorage_simple


class CheckParametersTestCase(TestCase):
    def test_accepts_allowed_optional_parameters(self):
        MeteologgerStorage_simple(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "simple",
                "fields": "5, 6",
                "nullstr": "NULL",
                "delimiter": ",",
                "date_format": "%Y-%m-%d %H:%M",
                "nfields_to_ignore": 2,
            }
        )


class ExtractTimestampTestCase(TestCase):
    def setUp(self):
        dummy_logger = logging.getLogger("dummy")
        dummy_logger.addHandler(logging.NullHandler())
        self.meteologger_storage = MeteologgerStorage_simple(
            {
                "station_id": 1334,
                "path": "/foo/bar",
                "storage_format": "simple",
                "fields": "5, 6",
                "nullstr": "NULL",
                "delimiter": ",",
                "date_format": "%d/%m/%Y %H:%M",
                "nfields_to_ignore": 2,
            },
            logger=dummy_logger,
        )

    def test_extracts_timestamp_with_time_included(self):
        self.assertEqual(
            self.meteologger_storage._extract_timestamp(
                "ign1,ign2,28/2/2019 13:47,25.2,42.3\n"
            ),
            dt.datetime(2019, 2, 28, 13, 47),
        )
        self.assertFalse(self.meteologger_storage._separate_time)

    def test_extracts_timestamp_separate_time(self):
        self.assertEqual(
            self.meteologger_storage._extract_timestamp(
                "ign1,ign2,28/2/2019,13:47,25.2,42.3\n"
            ),
            dt.datetime(2019, 2, 28, 13, 47),
        )
        self.assertTrue(self.meteologger_storage._separate_time)

    def test_raises_error_on_invalid_date(self):
        with self.assertRaises(MeteologgerStorageReadError):
            self.meteologger_storage._extract_timestamp(
                "ign1,ign2,29/2/2019 13:47,25.2,42.3\n"
            )

    def test_ignores_leading_spaces(self):
        self.assertEqual(
            self.meteologger_storage._extract_timestamp(
                "ign1,ign2, 28/2/2019 13:47,25.2,42.3\n"
            ),
            dt.datetime(2019, 2, 28, 13, 47),
        )
        self.assertFalse(self.meteologger_storage._separate_time)

    def test_ignores_trailing_spaces(self):
        self.assertEqual(
            self.meteologger_storage._extract_timestamp(
                "ign1,ign2,28/2/2019 13:47 ,25.2,42.3\n"
            ),
            dt.datetime(2019, 2, 28, 13, 47),
        )
        self.assertFalse(self.meteologger_storage._separate_time)

    def test_ignores_double_quotes(self):
        self.assertEqual(
            self.meteologger_storage._extract_timestamp(
                'ign1,ign2,"28/2/2019 13:47",25.2,42.3\n'
            ),
            dt.datetime(2019, 2, 28, 13, 47),
        )
        self.assertFalse(self.meteologger_storage._separate_time)

    def test_ignores_leading_spaces_before_opening_quote(self):
        self.assertEqual(
            self.meteologger_storage._extract_timestamp(
                'ign1,ign2, "28/2/2019 13:47",25.2,42.3\n'
            ),
            dt.datetime(2019, 2, 28, 13, 47),
        )
        self.assertFalse(self.meteologger_storage._separate_time)

    def test_ignores_trailing_spaces_after_closing_quote(self):
        self.assertEqual(
            self.meteologger_storage._extract_timestamp(
                'ign1,ign2,"28/2/2019 13:47" ,25.2,42.3\n'
            ),
            dt.datetime(2019, 2, 28, 13, 47),
        )
        self.assertFalse(self.meteologger_storage._separate_time)

    def test_ignores_leading_spaces_after_opening_quote(self):
        self.assertEqual(
            self.meteologger_storage._extract_timestamp(
                'ign1,ign2," 28/2/2019 13:47",25.2,42.3\n'
            ),
            dt.datetime(2019, 2, 28, 13, 47),
        )
        self.assertFalse(self.meteologger_storage._separate_time)

    def test_ignores_trailing_spaces_before_closing_quote(self):
        self.assertEqual(
            self.meteologger_storage._extract_timestamp(
                'ign1,ign2,"28/2/2019 13:47 ",25.2,42.3\n'
            ),
            dt.datetime(2019, 2, 28, 13, 47),
        )
        self.assertFalse(self.meteologger_storage._separate_time)


class GetItemFromLineTestCase(TestCase):
    def setUp(self):
        dummy_logger = logging.getLogger("dummy")
        dummy_logger.addHandler(logging.NullHandler())
        self.meteologger_storage = MeteologgerStorage_simple(
            {
                "station_id": 1334,
                "path": "/foo/bar",
                "storage_format": "simple",
                "fields": "5, 6",
                "nullstr": "NULL",
                "delimiter": ",",
                "date_format": "%d/%m/%Y %H:%M",
                "nfields_to_ignore": 2,
            },
            logger=dummy_logger,
        )
        self.meteologger_storage._separate_time = False

    def test_get_first_item(self):
        r = self.meteologger_storage._get_item_from_line(
            "ign1,ign2,28/2/2019 13:47,25.2,42.3\n", 1
        )
        self.assertAlmostEqual(r[0], 25.2)
        self.assertEqual(r[1], "")

    def test_get_second_item(self):
        r = self.meteologger_storage._get_item_from_line(
            "ign1,ign2,28/2/2019 13:47,25.2,42.3\n", 2
        )
        self.assertAlmostEqual(r[0], 42.3)
        self.assertEqual(r[1], "")

    def test_get_null_item(self):
        r = self.meteologger_storage._get_item_from_line(
            "ign1,ign2,28/2/2019 13:47,NULL,42.3\n", 1
        )
        self.assertTrue(math.isnan(r[0]))
        self.assertEqual(r[1], "")

    def test_raises_error_on_invalid_number(self):
        with self.assertRaises(ValueError):
            self.meteologger_storage._get_item_from_line(
                "ign1,ign2,28/2/2019 13:47,hello,42.3\n", 1
            )
