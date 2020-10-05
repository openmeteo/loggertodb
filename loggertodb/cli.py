import configparser
import datetime as dt
import logging
import sys
import traceback

import click

from . import __version__, meteologgerstorage
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
@click.argument("configfile")
@click.version_option(version=__version__, prog_name="loggertodb")
def main(upgrade, configfile):
    """Insert meteorological logger data to Enhydris"""
    if upgrade:
        ConfigFile(configfile).upgrade()
    else:
        LoggerToDb(configfile).run()


class LoggerToDb:
    def __init__(self, configfile):
        self.configfile = configfile
        self.logging_system = Logging()

    def run(self):
        try:
            self.configuration = Configuration(self.configfile, self.logging_system)
            self.configuration.read()
            self.logging_system.setup_logger(self.configuration)
            self.logging_system.log_start_of_execution()
            self.enhydris = Enhydris(self.configuration)
            self._process_stations()
            self.logging_system.log_end_of_execution()
        except Exception as e:
            self.logging_system.logger.error(str(e))
            self.logging_system.logger.debug(traceback.format_exc())
            raise click.ClickException(str(e))

    def _process_stations(self):
        for meteologger_storage in self.configuration.meteologger_storages:
            try:
                self.enhydris.upload(meteologger_storage)
            except LoggerToDbError as e:
                msg = "Error while processing item {}: {}".format(
                    meteologger_storage.section, str(e)
                )
                sys.stderr.write(msg + "\n")
                self.logging_system.logger.error(msg)
                self.logging_system.logger.debug(traceback.format_exc())


class Logging:
    def __init__(self):
        self.logger = logging.getLogger("loggertodb")
        self.stdout_handler = logging.StreamHandler()
        self.logger.addHandler(self.stdout_handler)

    def setup_logger(self, configuration):
        self.logger.setLevel(configuration.loglevel.upper())
        if configuration.logfile:
            self.logger.removeHandler(self.stdout_handler)
            self.logger.addHandler(logging.FileHandler(configuration.logfile))

    def log_start_of_execution(self):
        self.logger.info("Starting loggertodb, " + dt.datetime.today().isoformat())

    def log_end_of_execution(self):
        self.logger.info("Finished loggertodb, " + dt.datetime.today().isoformat())


class Configuration:
    def __init__(self, configfile, logging_system):
        self.logging_system = logging_system
        self.configfile = configfile
        self.config = configparser.ConfigParser(interpolation=None)
        with open(self.configfile) as f:
            self.config.read_file(f)
        self.meteologger_storages = []

    def read(self):
        self._read_general_section()
        self._read_station_sections()

    def _read_general_section(self):
        self.base_url = self.config.get("General", "base_url")
        self.auth_token = self.config.get("General", "auth_token")
        self.logfile = self.config.get("General", "logfile", fallback="")
        self.loglevel = self.config.get("General", "loglevel", fallback="warning")
        log_levels = ("ERROR", "WARNING", "INFO", "DEBUG")
        if self.loglevel.upper() not in log_levels:
            raise WrongValueError("loglevel must be one of " + ", ".join(log_levels))

    def _read_station_sections(self):
        station_section_names = [n for n in self.config.sections() if n != "General"]
        if not len(station_section_names):
            raise configparser.NoSectionError("No stations have been specified")
        for section_name in station_section_names:
            section = self.config[section_name]
            klassname = "MeteologgerStorage_" + section["storage_format"]
            if not hasattr(meteologgerstorage, klassname):
                raise UnsupportedFormat(section["storage_format"])
            klass = getattr(meteologgerstorage, klassname)
            self.meteologger_storages.append(
                klass(section, logger=self.logging_system.logger)
            )


if __name__ == "__main__":
    sys.exit(main())
