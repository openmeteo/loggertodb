import os
import textwrap
from tempfile import NamedTemporaryFile
from unittest import TestCase
from unittest.mock import patch

from click.testing import CliRunner

from loggertodb import LoggerToDbError, cli
from loggertodb.cli import LoggerToDb


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


class ConfigurationWithWrongMaxRecordsTestCase(TestCase):
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
                        max_records = hello
                        """
                    )
                )
            self.result = runner.invoke(cli.main, ["loggertodb.conf"])

    def test_exit_status(self):
        self.assertEqual(self.result.exit_code, 1)

    def test_error_message(self):
        self.assertIn("Wrong max_records: must be an integer", self.result.stderr)


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


class UploadErrorTestCase(TestCase):
    config = textwrap.dedent(
        """\
        [General]
        base_url = https://example.com
        auth_token = 123456789abcdef0123456789abcdef012345678

        [My station]
        storage_format = simple
        station_id = 1334
        path = .
        fields = 1,2,3
        timezone = Europe/Athens
        """
    )

    @patch("loggertodb.cli.logging")
    @patch("loggertodb.cli.sys.stderr.write")
    @patch("loggertodb.cli.Enhydris")
    def setUp(self, mock_enhydris, mock_stderr_write, mock_logging):
        self.mock_enhydris = mock_enhydris
        self.mock_stderr_write = mock_stderr_write
        self.mock_logging = mock_logging
        self.mock_enhydris.return_value.upload.side_effect = LoggerToDbError(
            "hello world"
        )

        # NamedTemporaryFile with delete=True is essentially broken on Windows,
        # therefore we manually delete ourselves. See
        # https://stackoverflow.com/questions/49868470/using-namedtemporaryfile
        # for more information.
        tmpfilename = None
        try:
            with NamedTemporaryFile("w", delete=False) as tmpfile:
                tmpfile.write(self.config)
                tmpfile.seek(0)
                tmpfilename = tmpfile.name
            LoggerToDb(tmpfile.name).run()
        finally:
            if tmpfilename is not None:
                os.remove(tmpfilename)

    def test_writes_error_to_stderr(self):
        self.mock_stderr_write.assert_called_with(
            "Error while processing item My station: hello world\n"
        )

    def test_logs_error(self):
        self.mock_logging.getLogger.return_value.error.assert_called_with(
            "Error while processing item My station: hello world"
        )

    def test_logs_traceback(self):
        arg = self.mock_logging.getLogger.return_value.debug.call_args[0][0]
        self.assertTrue("Traceback" in arg)
