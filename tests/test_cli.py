import datetime as dt
import os
import textwrap
from unittest import TestCase
from unittest.mock import call, patch

from click.testing import CliRunner

from loggertodb import cli


class NonExistentConfigFileTestCase(TestCase):
    def setUp(self):
        runner = CliRunner(mix_stderr=False)
        self.result = runner.invoke(cli.main, ["nonexistent.conf"])

    def test_exit_status(self):
        self.assertEqual(self.result.exit_code, 1)

    def test_error_message(self):
        self.assertIn(
            "No such file or directory: 'nonexistent.conf'", self.result.stderr
        )


class MissingBaseUrlTestCase(TestCase):
    def setUp(self):
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            with open("loggertodb.conf", "w") as f:
                f.write(
                    textwrap.dedent(
                        """\
                        [General]
                        username = a_user
                        password = a_password
                        """
                    )
                )
            self.result = runner.invoke(cli.main, ["loggertodb.conf"])

    def test_exit_status(self):
        self.assertEqual(self.result.exit_code, 1)

    def test_error_message(self):
        self.assertIn("No option 'base_url' in section: 'General'", self.result.stderr)


class NonExistentLogLevelTestCase(TestCase):
    def setUp(self):
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            with open("loggertodb.conf", "w") as f:
                f.write(
                    textwrap.dedent(
                        """\
                        [General]
                        base_url = https://example.com
                        username = a_user
                        password = a_password
                        loglevel = NONEXISTENT_LOG_LEVEL
                        """
                    )
                )
            self.result = runner.invoke(cli.main, ["loggertodb.conf"])

    def test_exit_status(self):
        self.assertEqual(self.result.exit_code, 1)

    def test_error_message(self):
        self.assertIn(
            "loglevel must be one of ERROR, WARNING, INFO, DEBUG", self.result.stderr
        )


class ConfigurationWithNoMeteologgersTestCase(TestCase):
    def setUp(self):
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            with open("loggertodb.conf", "w") as f:
                f.write(
                    textwrap.dedent(
                        """\
                        [General]
                        base_url = https://example.com
                        username = a_user
                        password = a_password
                        """
                    )
                )
            self.result = runner.invoke(cli.main, ["loggertodb.conf"])

    def test_exit_status(self):
        self.assertEqual(self.result.exit_code, 1)

    def test_error_message(self):
        self.assertIn("No stations have been specified", self.result.stderr)


class ConfigurationWithUnsupportedFormatTestCase(TestCase):
    @patch("loggertodb.cli.EnhydrisApiClient")
    def setUp(self, mock_client):
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            with open("loggertodb.conf", "w") as f:
                f.write(
                    textwrap.dedent(
                        """\
                        [General]
                        base_url = https://example.com
                        username = a_user
                        password = a_password

                        [My station]
                        storage_format = unsupported
                        """
                    )
                )
            self.result = runner.invoke(cli.main, ["loggertodb.conf"])

    def test_exit_status(self):
        self.assertEqual(self.result.exit_code, 1)

    def test_error_message(self):
        self.assertIn("Unsupported format 'unsupported'", self.result.stderr)


class CorrectConfigurationTestCase(TestCase):
    @patch("loggertodb.cli.EnhydrisApiClient")
    @patch("loggertodb.cli.update_database")
    @patch("loggertodb.meteologgerstorage.MeteologgerStorage_simple")
    def setUp(self, mock_meteologgerstorage, mock_update_db, mock_client):
        self.mock_meteologgerstorage = mock_meteologgerstorage
        self.mock_update_db = mock_update_db
        self.mock_client = mock_client
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            with open("loggertodb.conf", "w") as f:
                f.write(
                    textwrap.dedent(
                        """\
                        [General]
                        base_url = https://example.com
                        username = a_user
                        password = a_password

                        [My station]
                        storage_format = simple
                        station_id = 1334
                        path = .
                        fields = 1,2,3
                        """
                    )
                )
            self.result = runner.invoke(cli.main, ["loggertodb.conf"])

    def test_exit_status(self):
        self.assertEqual(self.result.exit_code, 0)

    def test_has_used_base_url(self):
        self.mock_client.assert_called_once_with("https://example.com")

    def test_has_logged_on(self):
        self.mock_client.return_value.login.assert_called_once_with(
            "a_user", "a_password"
        )

    def test_has_updated_database(self):
        self.mock_update_db.assert_called_once_with(
            self.mock_client.return_value, self.mock_meteologgerstorage.return_value
        )


class CorrectConfigurationWithLogFileTestCase(TestCase):
    @patch("loggertodb.cli.EnhydrisApiClient")
    @patch("loggertodb.cli.update_database")
    @patch("loggertodb.meteologgerstorage.MeteologgerStorage_simple")
    def test_creates_log_file(self, *args):
        self.mock_meteologgerstorage = args[0]
        self.mock_update_db = args[1]
        self.mock_client = args[2]
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            with open("loggertodb.conf", "w") as f:
                f.write(
                    textwrap.dedent(
                        """\
                        [General]
                        base_url = https://example.com
                        username = a_user
                        password = a_password
                        logfile = deleteme

                        [My station]
                        storage_format = simple
                        station_id = 1334
                        path = .
                        fields = 1,2,3
                        """
                    )
                )
            self.result = runner.invoke(cli.main, ["loggertodb.conf"])
            self.assertTrue(os.path.exists("deleteme"))


class UpdateDatabaseTestCase(TestCase):
    @patch("loggertodb.cli.EnhydrisApiClient")
    @patch("loggertodb.cli.meteologgerstorage.MeteologgerStorage_simple")
    @patch("loggertodb.cli.HTimeseries", new=lambda x: x)
    def setUp(self, mock_meteologgerstorage, mock_client):
        # Configure EnhydrisApiClient mock
        self.mock_client = mock_client
        attrs = {
            "return_value.get_ts_end_date.return_value": dt.datetime(2019, 3, 5, 7, 20)
        }
        self.mock_client.configure_mock(**attrs)

        # Configure MeteologgerStorage mock
        self.mock_meteologgerstorage = mock_meteologgerstorage
        attrs = {
            "return_value.timeseries_ids": {1, 2, 3},
            "return_value.get_recent_data.side_effect": [
                "new data for timeseries_id=1",
                "new data for timeseries_id=2",
                "new data for timeseries_id=3",
            ],
        }
        self.mock_meteologgerstorage.configure_mock(**attrs)

        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            with open("loggertodb.conf", "w") as f:
                f.write(
                    textwrap.dedent(
                        """\
                        [General]
                        base_url = https://example.com
                        username = a_user
                        password = a_password

                        [My station]
                        storage_format = simple
                        station_id = 1334
                        path = .
                        fields = 1,2,3
                        """
                    )
                )
            runner.invoke(cli.main, ["loggertodb.conf"])

    def test_called_get_recent_data_as_needed(self):
        self.mock_meteologgerstorage.return_value.get_recent_data.assert_has_calls(
            [
                call(1, dt.datetime(2019, 3, 5, 7, 20)),
                call(2, dt.datetime(2019, 3, 5, 7, 20)),
                call(3, dt.datetime(2019, 3, 5, 7, 20)),
            ]
        )

    def test_called_post_tsdata_as_needed(self):
        self.mock_client.post_tsdata.has_calls(
            [
                call(1, "new data for timeseries_id=1"),
                call(2, "new data for timeseries_id=2"),
                call(3, "new data for timeseries_id=3"),
            ]
        )
