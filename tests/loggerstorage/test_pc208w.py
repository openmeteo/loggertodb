import datetime as dt
import logging
import math
from unittest import TestCase

from loggertodb.exceptions import ConfigurationError, MeteologgerStorageReadError
from loggertodb.meteologgerstorage import MeteologgerStorage_pc208w


class CheckParametersTestCase(TestCase):
    def test_raises_error_on_subset_identifiers_missing(self):
        expected_error_message = 'Parameter "subset_identifiers" is required'
        with self.assertRaisesRegex(ConfigurationError, expected_error_message):
            MeteologgerStorage_pc208w(
                {
                    "station_id": 1334,
                    "path": "irrelevant",
                    "storage_format": "dummy",
                    "fields": "5, 6",
                }
            )


class ExtractTimestampTestCase(TestCase):
    def setUp(self):
        dummy_logger = logging.getLogger("dummy")
        dummy_logger.addHandler(logging.NullHandler())
        self.meteologger_storage = MeteologgerStorage_pc208w(
            {
                "station_id": 1334,
                "path": "/foo/bar",
                "storage_format": "pc208w",
                "fields": "5, 6",
                "nullstr": "NULL",
                "subset_identifiers": "18",
            },
            logger=dummy_logger,
        )

    def test_extracts_timestamp(self):
        self.assertEqual(
            self.meteologger_storage._extract_timestamp(
                "18,185,2019,59,1347,25.2,42.3\n"
            ),
            dt.datetime(2019, 2, 28, 13, 47),
        )

    def test_raises_error_on_invalid_date(self):
        with self.assertRaises(MeteologgerStorageReadError):
            self.meteologger_storage._extract_timestamp(
                "18,185,2019a,59,1347,25.2,42.3\n"
            )


class GetItemFromLineTestCase(TestCase):
    def setUp(self):
        dummy_logger = logging.getLogger("dummy")
        dummy_logger.addHandler(logging.NullHandler())
        self.meteologger_storage = MeteologgerStorage_pc208w(
            {
                "station_id": 1334,
                "path": "/foo/bar",
                "storage_format": "pc208w",
                "fields": "5, 6",
                "nullstr": "NULL",
                "subset_identifiers": "18",
            },
            logger=dummy_logger,
        )

    def test_get_first_item(self):
        r = self.meteologger_storage._get_item_from_line(
            "18,185,2019,59,1347,25.2,42.3\n", 1
        )
        self.assertAlmostEqual(r[0], 25.2)
        self.assertEqual(r[1], "")

    def test_get_second_item(self):
        r = self.meteologger_storage._get_item_from_line(
            "18,185,2019,59,1347,25.2,42.3\n", 2
        )
        self.assertAlmostEqual(r[0], 42.3)
        self.assertEqual(r[1], "")

    def test_get_null_item(self):
        r = self.meteologger_storage._get_item_from_line(
            "18,185,2019,59,1347,NULL,42.3\n", 1
        )
        self.assertTrue(math.isnan(r[0]))
        self.assertEqual(r[1], "")

    def test_raises_error_on_invalid_number(self):
        with self.assertRaises(ValueError):
            self.meteologger_storage._get_item_from_line(
                "18,185,2019,59,1347,hello,42.3\n", 1
            )


class SubsetIdentifiersMatchTestCase(TestCase):
    def setUp(self):
        dummy_logger = logging.getLogger("dummy")
        dummy_logger.addHandler(logging.NullHandler())
        self.meteologger_storage = MeteologgerStorage_pc208w(
            {
                "station_id": 1334,
                "path": "/foo/bar",
                "storage_format": "pc208w",
                "fields": "5, 6",
                "nullstr": "NULL",
                "subset_identifiers": "18",
            },
            logger=dummy_logger,
        )

    def test_matches(self):
        self.assertTrue(
            self.meteologger_storage._subset_identifiers_match(
                "18,185,2019,59,1347,25.2,42.3\n"
            )
        )

    def test_does_not_match(self):
        self.assertFalse(
            self.meteologger_storage._subset_identifiers_match(
                "19,185,2019,59,1347,25.2,42.3\n"
            )
        )
