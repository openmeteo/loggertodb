import configparser
import datetime as dt
import logging
import sys
import traceback
from typing import Any

import click

from . import meteologgerstorage
from ._version import __version__
from .enhydris import Enhydris
from .exceptions import LoggerToDbError
from .upgrade import ConfigFile


class WrongValueError(configparser.Error):
    pass


class UnsupportedFormat(Exception):
    def __str__(self):
        return "Unsupported format '{}'".format(self.args[0])


@click.command()
@click.option(
    "--upgrade", is_flag=True, default=False, help="Upgrade configuration file"
)
@click.option("--insert-all", nargs=2, type=str, help="Insert old data retroactively")
@click.argument("configfile")
@click.version_option(version=__version__, prog_name="loggertodb")
def main(upgrade: bool, insert_all: tuple[str, str] | None, configfile: str):
    """Insert meteorological logger data to Enhydris"""
    if upgrade:
        ConfigFile(configfile).upgrade()
    else:
        LoggerToDb(configfile, insert_all).run()


class LoggerToDb:
    def __init__(self, configfile: str, insert_all: tuple[str, str] | None):
        self.configfile = configfile
        self.logging_system = Logging()
        self.insert_all = insert_all

    def run(self):
        try:
            self.configuration = Configuration(
                self.configfile, self.logging_system, self.insert_all
            )
            self.configuration.read()
            self.logging_system.setup_logger(self.configuration)
            self.logging_system.log_start_of_execution()
            self.enhydris = Enhydris(
                self.configuration,
                self.logging_system.logger,
                self.insert_all is not None,
            )
            self._process_all_stations()
            self.logging_system.log_end_of_execution()
        except Exception as e:
            self.logging_system.logger.error(str(e))
            self.logging_system.logger.debug(traceback.format_exc())
            raise click.ClickException(str(e))

    def _process_all_stations(self):
        config = self.configuration
        for sectionname, meteologger_storage in config.meteologger_storages.items():
            section = config.config[sectionname]
            try:
                self.logging_system.logger.info(f"*** Processing item {section.name}")
                self.enhydris.upload(meteologger_storage)
                self.logging_system.logger.info(f"Finished item {section.name}")
            except LoggerToDbError as e:
                msg = f"Error while processing item {section.name}: {str(e)}"
                sys.stderr.write(msg + "\n")
                self.logging_system.logger.error(msg)
                self.logging_system.logger.debug(traceback.format_exc())


class Logging:
    def __init__(self):
        self.logger = logging.getLogger("loggertodb")
        self.stdout_handler = logging.StreamHandler()
        self.logger.addHandler(self.stdout_handler)

    def setup_logger(self, configuration: "Configuration"):
        self.logger.setLevel(configuration.loglevel.upper())
        if configuration.logfile:
            self.logger.removeHandler(self.stdout_handler)
            self.logger.addHandler(logging.FileHandler(configuration.logfile))

    def log_start_of_execution(self):
        self.logger.info(
            f"****** Starting loggertodb, {dt.datetime.today().isoformat()}"
        )

    def log_end_of_execution(self):
        self.logger.info("Finished loggertodb, " + dt.datetime.today().isoformat())


class Configuration:
    def __init__(
        self,
        configfile: str,
        logging_system: Logging,
        insert_all: tuple[str, str] | None,
    ):
        self.logging_system = logging_system
        self.configfile = configfile
        self.config = configparser.ConfigParser(interpolation=None)
        with open(self.configfile) as f:
            self.config.read_file(f)
        self.insert_all = insert_all
        self.meteologger_storages: dict[str, Any] = {}

    def read(self):
        self._read_general_section()
        self._read_station_sections()

    def _read_general_section(self):
        self.base_url = self.config.get("General", "base_url")
        self.auth_token = self.config.get("General", "auth_token")
        self.logfile = self.config.get("General", "logfile", fallback="")
        self.loglevel = self.config.get("General", "loglevel", fallback="warning")
        try:
            fallback = 1_000_000_000 if self.insert_all else 10_000
            self.max_records = self.config.getint(
                "General", "max_records", fallback=fallback
            )
        except ValueError:
            raise WrongValueError("Wrong max_records: must be an integer")
        log_levels = ("ERROR", "WARNING", "INFO", "DEBUG")
        if self.loglevel.upper() not in log_levels:
            raise WrongValueError("loglevel must be one of " + ", ".join(log_levels))

    def _read_station_sections(self):
        station_section_names = [n for n in self.config.sections() if n != "General"]
        if not len(station_section_names):
            raise configparser.NoSectionError(
                "No stations have been specified in the configuration file"
            )
        if self.insert_all:
            insert_all_section, insert_all_filepath = self.insert_all
            if insert_all_section not in station_section_names:
                raise configparser.NoSectionError(
                    f"Section '{insert_all_section}' not found in configuration file"
                )
            section = self.config[insert_all_section]
            section["path"] = insert_all_filepath
            self._read_station_section(section)
        else:
            for section_name in station_section_names:
                section = self.config[section_name]
                self._read_station_section(section)

    def _read_station_section(self, section: configparser.SectionProxy):
        klassname = "MeteologgerStorage_" + section["storage_format"]
        if not hasattr(meteologgerstorage, klassname):
            raise UnsupportedFormat(section["storage_format"])
        klass = getattr(meteologgerstorage, klassname)
        self.meteologger_storages[section.name] = klass(
            section,
            max_records=self.max_records,
            logger=self.logging_system.logger,
        )


if __name__ == "__main__":
    sys.exit(main())
