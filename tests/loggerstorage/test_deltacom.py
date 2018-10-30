import datetime as dt
import logging
import math
from unittest import TestCase

from loggertodb.exceptions import MeteologgerStorageReadError
from loggertodb.meteologgerstorage import MeteologgerStorage_deltacom


class ExtractTimestampTestCase(TestCase):
    def setUp(self):
        dummy_logger = logging.getLogger("dummy")
        dummy_logger.addHandler(logging.NullHandler())
        self.meteologger_storage = MeteologgerStorage_deltacom(
            {
                "station_id": 1334,
                "path": "/foo/bar",
                "storage_format": "deltacom",
                "fields": "5, 6",
                "nullstr": "NULL",
            },
            logger=dummy_logger,
        )

    def test_extracts_timestamp(self):
        self.assertEqual(
            self.meteologger_storage._extract_timestamp("2019-02-28T13:47 25.2 42.3\n"),
            dt.datetime(2019, 2, 28, 13, 47),
        )

    def test_raises_error_on_invalid_date(self):
        with self.assertRaises(MeteologgerStorageReadError):
            self.meteologger_storage._extract_timestamp("2019-02-29T13:47 25.2 42.3\n"),


class GetItemFromLineTestCase(TestCase):
    def setUp(self):
        dummy_logger = logging.getLogger("dummy")
        dummy_logger.addHandler(logging.NullHandler())
        self.meteologger_storage = MeteologgerStorage_deltacom(
            {
                "station_id": 1334,
                "path": "/foo/bar",
                "storage_format": "deltacom",
                "fields": "5, 6",
                "nullstr": "NULL",
            },
            logger=dummy_logger,
        )

    def test_get_first_item(self):
        r = self.meteologger_storage._get_item_from_line(
            "2019-02-28T13:47 25.2 42.3\n", 1
        )
        self.assertAlmostEqual(r[0], 25.2)
        self.assertEqual(r[1], "")

    def test_get_second_item(self):
        r = self.meteologger_storage._get_item_from_line(
            "2019-02-28T13:47 25.2 42.3\n", 2
        )
        self.assertAlmostEqual(r[0], 42.3)
        self.assertEqual(r[1], "")

    def test_get_item_with_overrun(self):
        r = self.meteologger_storage._get_item_from_line(
            "2019-02-28T13:47 25.2# 42.3\n", 1
        )
        self.assertAlmostEqual(r[0], 25.2)
        self.assertEqual(r[1], "LOGOVERRUN")

    def test_get_item_with_noisy(self):
        r = self.meteologger_storage._get_item_from_line(
            "2019-02-28T13:47 25.2$ 42.3\n", 1
        )
        self.assertAlmostEqual(r[0], 25.2)
        self.assertEqual(r[1], "LOGNOISY")

    def test_get_item_with_outside(self):
        r = self.meteologger_storage._get_item_from_line(
            "2019-02-28T13:47 25.2% 42.3\n", 1
        )
        self.assertAlmostEqual(r[0], 25.2)
        self.assertEqual(r[1], "LOGOUTSIDE")

    def test_get_item_with_range(self):
        r = self.meteologger_storage._get_item_from_line(
            "2019-02-28T13:47 25.2& 42.3\n", 1
        )
        self.assertAlmostEqual(r[0], 25.2)
        self.assertEqual(r[1], "LOGRANGE")

    def test_raises_error_on_invalid_flag(self):
        with self.assertRaises(ValueError):
            self.meteologger_storage._get_item_from_line(
                "2019-02-28T13:47 25.2! 42.3\n", 1
            )

    def test_get_null_item(self):
        r = self.meteologger_storage._get_item_from_line(
            "2019-02-28T13:47 NULL 42.3\n", 1
        )
        self.assertTrue(math.isnan(r[0]))
        self.assertEqual(r[1], "")
