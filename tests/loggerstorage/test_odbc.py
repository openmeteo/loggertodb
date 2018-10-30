import datetime as dt
from unittest import TestCase
from unittest.mock import call, patch

from loggertodb.exceptions import ConfigurationError
from loggertodb.meteologgerstorage import MeteologgerStorage_odbc


class ConfigurationTestCase(TestCase):
    def test_raises_error_on_table_missing(self):
        expected_error_message = 'Parameter "table" is required'
        with self.assertRaisesRegex(ConfigurationError, expected_error_message):
            MeteologgerStorage_odbc(
                {
                    "station_id": 1334,
                    "path": "irrelevant",
                    "storage_format": "odbc",
                    "fields": "5, 6",
                    "date_sql": "irrelevant",
                    "data_columns": "irrelevant",
                }
            )

    def test_raises_error_on_date_sql_missing(self):
        expected_error_message = 'Parameter "date_sql" is required'
        with self.assertRaisesRegex(ConfigurationError, expected_error_message):
            MeteologgerStorage_odbc(
                {
                    "station_id": 1334,
                    "path": "irrelevant",
                    "storage_format": "odbc",
                    "fields": "5, 6",
                    "table": "irrelevant",
                    "data_columns": "irrelevant",
                }
            )

    def test_raises_error_on_data_columns_missing(self):
        expected_error_message = 'Parameter "data_columns" is required'
        with self.assertRaisesRegex(ConfigurationError, expected_error_message):
            MeteologgerStorage_odbc(
                {
                    "station_id": 1334,
                    "path": "irrelevant",
                    "storage_format": "odbc",
                    "fields": "5, 6",
                    "table": "irrelevant",
                    "date_sql": "irrelevant",
                }
            )

    def test_accepts_optional_parameters(sef):
        MeteologgerStorage_odbc(
            {
                "station_id": 1334,
                "path": "irrelevant",
                "storage_format": "odbc",
                "fields": "5, 6",
                "table": "irrelevant",
                "date_sql": "irrelevant",
                "data_columns": "irrelevant",
                "date_format": "irrelevant",
                "decimal_separator": "irrelevant",
            }
        )


class GetStorageTailTestCase(TestCase):
    @patch("loggertodb.meteologgerstorage.pyodbc")
    @patch("loggertodb.meteologgerstorage.MeteologgerStorage._fix_dst")
    def setUp(self, m2, m1):
        # Configure pyodbc mock
        self.pyodbc = m1
        attrs = {
            "connect.return_value.cursor.return_value.__iter__.return_value": [
                ["2019-03-02 05:00;43.1;25.2"],
                ["2019-03-02 04:00;42.1;24.2"],
            ]
        }
        self.pyodbc.configure_mock(**attrs)

        # Configure _fix_dst mock
        self.patched_fix_dst = m2
        self.patched_fix_dst.configure_mock(side_effect=lambda x: x)

        self.meteologger_storage = MeteologgerStorage_odbc(
            {
                "station_id": 1334,
                "path": "Some ODBC path",
                "storage_format": "odbc",
                "fields": "5, 6",
                "table": "SomeSQLTable",
                "data_columns": "variable1,variable2",
                "date_format": "%Y-%m-%d %H:%M",
                "date_sql": "timestamp",
                "decimal_separator": ".",
            }
        )
        self.result = self.meteologger_storage._get_storage_tail(
            dt.datetime(2019, 3, 2, 3, 0)
        )

    def test_connected(self):
        self.pyodbc.connect.assert_called_once_with("Some ODBC path")

    def test_executed_sql(self):
        mock_execute = self.pyodbc.connect.return_value.cursor.return_value.execute
        mock_execute.assert_called_once_with(
            """SELECT timestamp + ';' + "variable1" + ';' + "variable2" """
            """FROM "SomeSQLTable" ORDER BY -id"""
        )

    def test_result_length(self):
        self.assertEqual(len(self.result), 2)

    def test_result_timestamp_1(self):
        self.assertEqual(self.result[0]["timestamp"], dt.datetime(2019, 3, 2, 4, 0))

    def test_result_line_1(self):
        self.assertEqual(self.result[0]["line"], "2019-03-02 04:00;42.1;24.2")

    def test_result_timestamp_2(self):
        self.assertEqual(self.result[1]["timestamp"], dt.datetime(2019, 3, 2, 5, 0))

    def test_result_line_2(self):
        self.assertEqual(self.result[1]["line"], "2019-03-02 05:00;43.1;25.2")

    def test_called_fix_dst(self):
        self.patched_fix_dst.assert_has_calls(
            [call(dt.datetime(2019, 3, 2, 5, 0)), call(dt.datetime(2019, 3, 2, 4, 0))]
        )
