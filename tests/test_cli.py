import os
import textwrap
from unittest import TestCase
from unittest.mock import patch

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
                        auth_token = 123456789abcdef0123456789abcdef012345678
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
                        auth_token = 123456789abcdef0123456789abcdef012345678
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
                        auth_token = 123456789abcdef0123456789abcdef012345678
                        """
                    )
                )
            self.result = runner.invoke(cli.main, ["loggertodb.conf"])

    def test_exit_status(self):
        self.assertEqual(self.result.exit_code, 1)

    def test_error_message(self):
        self.assertIn("No stations have been specified", self.result.stderr)


class ConfigurationWithUnsupportedFormatTestCase(TestCase):
    @patch("loggertodb.cli.Enhydris")
    def setUp(self, mock_enhydris):
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            with open("loggertodb.conf", "w") as f:
                f.write(
                    textwrap.dedent(
                        """\
                        [General]
                        base_url = https://example.com
                        auth_token = 123456789abcdef0123456789abcdef012345678

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
    @patch("loggertodb.cli.Enhydris")
    @patch("loggertodb.meteologgerstorage.MeteologgerStorage_simple")
    def setUp(self, mock_meteologgerstorage, mock_enhydris):
        self.mock_meteologgerstorage = mock_meteologgerstorage
        self.mock_enhydris = mock_enhydris
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            with open("loggertodb.conf", "w") as f:
                f.write(
                    textwrap.dedent(
                        """\
                        [General]
                        base_url = https://example.com
                        auth_token = 123456789abcdef0123456789abcdef012345678

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
        configuration = self.mock_enhydris.call_args[0][0]
        self.assertEqual(configuration.base_url, "https://example.com")

    def test_has_used_auth_token(self):
        configuration = self.mock_enhydris.call_args[0][0]
        self.assertEqual(
            configuration.auth_token, "123456789abcdef0123456789abcdef012345678"
        )

    def test_has_uploaded(self):
        self.mock_enhydris.return_value.upload.assert_called_once_with(
            self.mock_meteologgerstorage.return_value
        )


class CorrectConfigurationWithLogFileTestCase(TestCase):
    @patch("loggertodb.cli.Enhydris")
    @patch("loggertodb.meteologgerstorage.MeteologgerStorage_simple")
    def test_creates_log_file(self, *args):
        self.mock_meteologgerstorage = args[0]
        self.mock_enhydris = args[1]
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            with open("loggertodb.conf", "w") as f:
                f.write(
                    textwrap.dedent(
                        """\
                        [General]
                        base_url = https://example.com
                        auth_token = 123456789abcdef0123456789abcdef012345678
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
