import json
import os
import shutil
import textwrap
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest import TestCase
from unittest.mock import patch

import responses
from click.testing import CliRunner

from loggertodb import LoggerToDbError, cli
from loggertodb.cli import LoggerToDb, Configuration, Logging
from loggertodb.enhydris import Enhydris
from loggertodb.exceptions import MeteologgerStorageReadError


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


class UploadError2TestCase(TestCase):
    config = textwrap.dedent(
        f"""\
        [General]
        base_url = https://example.com
        auth_token = 68b8c95a8daa0dc630ee8abc151ede9e3fc73426

        [Bouficha]
        station_id = 2013
        path = {os.getcwd()}/temp_data/bouficha*.data
        storage_format = simple
        timezone = Europe/Athens
        fields = 598
        null = NAN
        delimiter = ,
        """
    )

    def setUp(self):
        os.makedirs("temp_data", exist_ok=True)
        config_file_path = os.path.join(os.getcwd(), "temp_data", "testloggertodb.conf")
        with open(config_file_path, "w") as config_file:
            config_file.write(self.config)

        file_names = ["bouficha1.data", "bouficha2.data", "bouficha3.data"]
        file_contents = [
            "2023-05-18 14:40,25.2,47,2\n2023-05-18 14:50,25.2,47,2\n2023-05-18 14:59,25.2,47,4\n2023-05-18 15:10,25.2,47,4\n2023-05-18 15:20,25.2,47,5\n2023-05-18 15:20,25.2,47,6\n",
            "2023-05-19 14:40,25.2,47,2\n2023-05-19 14:50,25.2,47,2\n2023-05-19 14:59,25.2,47,4\n2023-05-19 15:10,25.2,47,4\n2023-05-19 15:20,25.2,47,5\n2023-05-19 15:20,25.2,47,6\n",
            "2023-05-20 14:40,25.wwwwwwwwwww,47,2\n2023-05-29 14:40,25.2,47,0\n2023-05-29 14:50,25.2,47,0\n2023-05-29 14:59,25.2,47,0\n2023-05-29 15:10,25.2,47,0\n2023-05-29 15:20,25.2,47,0\n"
        ]

        # Create temporary directory
        temp_dir = os.path.join(os.getcwd(), "temp_data")
        os.makedirs(temp_dir, exist_ok=True)

        # Create data files
        for file_name, content in zip(file_names, file_contents):
            file_path = os.path.join(temp_dir, file_name)
            with open(file_path, "w") as file:
                file.write(content)

    @responses.activate
    def test_extract_data_with_multiple_files(self):
        response_body = {"results": [
            {'id': 9801, 'type': 'Initial', 'last_modified': '2019-12-06T07:32:29.484725-06:00', 'time_step': 'H',
             'publicly_available': True, 'timeseries_group': 598}]}
        responses.add(
            responses.GET,
            url="https://example.com/api/stations/2013/timeseriesgroups/598/timeseries/",
            body=json.dumps(response_body),
            status=200,
            content_type='application/json'
        )
        responses.add(
            responses.GET,
            url="https://example.com/api/stations/2013/timeseriesgroups/598/timeseries/9801/bottom/?timezone=Etc%2FGMT",
            body=json.dumps(response_body),
            status=200,
            content_type='application/json'
        )
        config_file_path = os.path.join(os.getcwd(), "temp_data", "testloggertodb.conf")
        logging_system = Logging()

        self.configuration = Configuration(Path(config_file_path), logging_system)
        self.configuration.read()

        self.enhydris = Enhydris(self.configuration)
        config = self.configuration

        with self.assertRaises(MeteologgerStorageReadError) as e:
            self.enhydris.upload(config.meteologger_storages[0])

        expected_error_message = f'{os.getcwd()}/temp_data/bouficha3.data: "2023-05-20 14:40,25.wwwwwwwwwww,47,2\n": parsing error while trying to read values: could not convert string to float: \'25.wwwwwwwwwww\''
        self.assertEqual(str(e.exception), expected_error_message)

    def tearDown(self):
        shutil.rmtree("temp_data", ignore_errors=True)
