import configparser
import filecmp
import os
import shutil
from urllib.parse import urljoin

import requests
from enhydris_api_client import EnhydrisApiClient

from .meteologgerstorage import MeteologgerStorage_wdat5

wdat5_parameters = [x.split()[1] for x in MeteologgerStorage_wdat5.wdat_record_format][
    5:
]
convertable_parameters = wdat5_parameters + ["fields"]


class ConfigFile:
    def __init__(self, filename):
        self.filename = filename

    def upgrade(self):
        self._read_config()
        self.api_client = EnhydrisApiClient(self.base_url)
        self._convert_username_and_password_to_api_token()
        self._convert_fields()
        self._backup_file()
        self._write_upgraded_file()

    def _read_config(self):
        self.config = configparser.ConfigParser(interpolation=None)
        with open(self.filename) as f:
            self.config.read_file(f)
        self.base_url = self.config.get("General", "base_url")

    def _convert_username_and_password_to_api_token(self):
        username = self.config.get("General", "username")
        password = self.config.get("General", "password")
        token = self.api_client.get_token(username, password)
        self.config.set("General", "auth_token", token)
        self.config.remove_option("General", "username")
        self.config.remove_option("General", "password")

    def _convert_fields(self):
        station_section_names = [n for n in self.config.sections() if n != "General"]
        for section_name in station_section_names:
            self._convert_section(section_name)

    def _convert_section(self, section_name):
        self.section_name = section_name
        self.station_id = self.config.get(section_name, "station_id")
        for parameter in convertable_parameters:
            self._convert_parameter(parameter)

    def _convert_parameter(self, parameter):
        value = self.config.get(self.section_name, parameter, fallback=None)
        if value is None:
            return
        timeseries_ids = [int(x.strip()) for x in value.split(",")]
        timeseries_group_ids = [
            self._get_timeseries_group(timeseries_id)
            for timeseries_id in timeseries_ids
        ]
        self.config.set(
            self.section_name,
            parameter,
            ",".join([str(x) for x in timeseries_group_ids]),
        )

    def _get_timeseries_group(self, timeseries_id):
        if timeseries_id == 0:
            return 0
        url = urljoin(
            self.api_client.base_url,
            f"api/stations/{self.station_id}/timeseries/{timeseries_id}/",
        )
        response = self.api_client.session.get(url)
        self._check_response(response)
        return response.json()["timeseries_group"]

    def _check_response(self, response):
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            if response.text:
                raise requests.HTTPError(f"{str(e)}. Server response: {response.text}")
            else:
                raise

    @property
    def backup_filename(self):
        return self.filename + ".bak"

    def _backup_file(self):
        backup_file_is_identical = os.path.exists(self.backup_filename) and filecmp.cmp(
            self.filename, self.backup_filename, shallow=False
        )
        if backup_file_is_identical:
            return
        if os.path.exists(self.backup_filename):
            raise RuntimeError(
                f"Cannot backup configuration file; {self.backup_filename} exists"
            )
        shutil.copy(self.filename, self.backup_filename)

    def _write_upgraded_file(self):
        with open(self.filename, "w") as f:
            self.config.write(f)
