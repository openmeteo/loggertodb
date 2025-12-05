import os
import shutil
import textwrap
from tempfile import NamedTemporaryFile, mkdtemp
from typing import Any
from unittest import TestCase
from unittest.mock import MagicMock, patch

from click import ClickException
from click.testing import CliRunner

from loggertodb import LoggerToDbError, cli
from loggertodb.cli import LoggerToDb


class NonExistentConfigFileTestCase(TestCase):
    def setUp(self):
        runner = CliRunner()
        self.result = runner.invoke(cli.main, ["nonexistent.conf"])

    def test_exit_status(self):
        self.assertEqual(self.result.exit_code, 1)

    def test_error_message(self):
        self.assertIn(
            "No such file or directory: 'nonexistent.conf'", self.result.stderr
        )


class MissingBaseUrlTestCase(TestCase):
    def setUp(self):
        runner = CliRunner()
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
        runner = CliRunner()
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
        runner = CliRunner()
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
    def setUp(self, mock_enhydris: MagicMock):
        runner = CliRunner()
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
    def setUp(self, mock_enhydris: MagicMock):
        runner = CliRunner()
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


@patch("loggertodb.cli.Enhydris")
@patch("loggertodb.meteologgerstorage.MeteologgerStorage_simple")
class CorrectConfigurationTestCase(TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.fs = self.runner.isolated_filesystem()
        self.fs.__enter__()
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

                    [My station 2]
                    storage_format = simple
                    station_id = 1335
                    path = hello
                    fields = 1,2,3
                    """
                )
            )

    def tearDown(self):
        self.fs.__exit__(None, None, None)

    def test_exit_status(self, m1: MagicMock, m2: MagicMock):
        result = self.runner.invoke(cli.main, ["loggertodb.conf"])
        self.assertEqual(result.exit_code, 0)

    def test_has_used_base_url(self, m1: MagicMock, m2: MagicMock):
        self.runner.invoke(cli.main, ["loggertodb.conf"])
        configuration = m2.call_args[0][0]
        self.assertEqual(configuration.base_url, "https://example.com")

    def test_has_used_auth_token(self, m1: MagicMock, m2: MagicMock):
        self.runner.invoke(cli.main, ["loggertodb.conf"])
        configuration = m2.call_args[0][0]
        self.assertEqual(
            configuration.auth_token, "123456789abcdef0123456789abcdef012345678"
        )

    def test_has_uploaded(self, m1: MagicMock, m2: MagicMock):
        self.runner.invoke(cli.main, ["loggertodb.conf"])
        self.assertEqual(
            m2.return_value.upload.call_args_list,
            [
                ((m1.return_value,), {}),
                ((m1.return_value,), {}),
            ],
        )

    def test_insert_all(self, m1: MagicMock, m2: MagicMock):
        self.runner.invoke(
            cli.main,
            [
                "--insert-all",
                "My station",
                "mydata.csv",
                "loggertodb.conf",
            ],
        )
        m2.return_value.upload.assert_called_once_with(m1.return_value)
        self.assertEqual(m2.call_args[0][2], True)
        self.assertEqual(m1.call_args[0][0]["path"], "mydata.csv")
        self.assertEqual(m2.call_args[0][0].max_records, 1_000_000_000)

    def test_fails_if_insert_all_section_not_found(self, m1: MagicMock, m2: MagicMock):
        result = self.runner.invoke(
            cli.main,
            [
                "--insert-all",
                "Nonexistent station",
                "mydata.csv",
                "loggertodb.conf",
            ],
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIn(
            "Section 'Nonexistent station' not found in configuration file",
            result.stderr,
        )


class CorrectConfigurationWithLogFileTestCase(TestCase):
    @patch("loggertodb.cli.Enhydris")
    @patch("loggertodb.meteologgerstorage.MeteologgerStorage_simple")
    def test_creates_log_file(self, m1: MagicMock, m2: MagicMock):
        self.mock_meteologgerstorage = m1
        self.mock_enhydris = m2
        runner = CliRunner()
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


@patch("loggertodb.cli.Enhydris")
class AllowOverlapsTestCase(TestCase):
    def setUp(self):
        self.tmpdir = mkdtemp()
        self.configpathname = os.path.join(self.tmpdir, "loggertodb.conf")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _run_with_config(self, config: str):
        with open(self.configpathname, "w") as tmpfile:
            tmpfile.write(config)
        LoggerToDb(self.configpathname, None).run()

    def test_no(self, *args: Any):
        self._run_with_config(
            textwrap.dedent(
                f"""\
                [General]
                base_url = https://example.com
                auth_token = 123456789abcdef0123456789abcdef012345678
                logfile = {self.configpathname}

                [My station]
                timezone = UTC
                storage_format = simple
                station_id = 1334
                path = .
                fields = 1,2,3
                allow_overlaps = No
                """
            )
        )
        # If it hasn't raised exception, it's OK

    def test_garbage(self, *args: Any):
        with self.assertRaises(ClickException):
            self._run_with_config(
                textwrap.dedent(
                    f"""\
                    [General]
                    base_url = https://example.com
                    auth_token = 123456789abcdef0123456789abcdef012345678
                    logfile = {self.configpathname}

                    [My station]
                    timezone = UTC
                    storage_format = simple
                    station_id = 1334
                    path = .
                    fields = 1,2,3
                    allow_overlaps = garbage
                    """
                )
            )


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
    def setUp(self, m1: MagicMock, m2: MagicMock, m3: MagicMock):
        self.mock_enhydris = m1
        self.mock_stderr_write = m2
        self.mock_logging = m3
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
            LoggerToDb(tmpfile.name, None).run()
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
