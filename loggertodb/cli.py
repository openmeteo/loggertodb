import configparser
import logging
import sys
import traceback
from datetime import datetime

import click
from enhydris_api_client import EnhydrisApiClient
from htimeseries import HTimeseries

from . import __version__, meteologgerstorage
from .exceptions import LoggerToDbError


class WrongValueError(configparser.Error):
    pass


class UnsupportedFormat(Exception):
    def __str__(self):
        return "Unsupported format '{}'".format(self.args[0])


@click.command()
@click.argument("configfile")
@click.version_option(version=__version__, prog_name="loggertodb")
def main(configfile):
    """Insert meteorological logger data to Enhydris"""

    # Start by setting logger to stdout; later we will switch it according to config
    logger = logging.getLogger("loggertodb")
    stdout_handler = logging.StreamHandler()
    logger.addHandler(stdout_handler)

    try:
        config = configparser.ConfigParser(interpolation=None)
        with open(configfile) as f:
            config.read_file(f)

        # Read the [General] section
        base_url = config.get("General", "base_url")
        username = config.get("General", "username")
        password = config.get("General", "password")
        logfile = config.get("General", "logfile", fallback="")
        loglevel = config.get("General", "loglevel", fallback="warning")
        log_levels = ("ERROR", "WARNING", "INFO", "DEBUG")
        if loglevel.upper() not in log_levels:
            raise WrongValueError("loglevel must be one of " + ", ".join(log_levels))

        # Remove [General] and make sure there are more sections
        config.pop("General")
        if not len(config.sections()):
            raise configparser.NoSectionError("No stations have been specified")

        # Setup logger
        logger.setLevel(loglevel.upper())
        if logfile:
            logger.removeHandler(stdout_handler)
            logger.addHandler(logging.FileHandler(logfile))

        # Log start of execution
        logger.info("Starting loggertodb, " + datetime.today().isoformat())

        # Connect to Enhydris
        client = EnhydrisApiClient(base_url)
        client.login(username, password)

        # Read each section and do the work for it
        for section_name in config.sections():
            section = config[section_name]
            klassname = "MeteologgerStorage_" + section["storage_format"]
            if not hasattr(meteologgerstorage, klassname):
                raise UnsupportedFormat(section["storage_format"])
            klass = getattr(meteologgerstorage, klassname)
            meteologger_storage = klass(section, logger=logger)
            try:
                update_database(client, meteologger_storage)
            except LoggerToDbError as e:
                msg = "Error while processing item {}: {}".format(section, str(e))
                sys.stderr.write(msg + "\n")
                logger.error(msg)
                logger.debug(traceback.format_exc())

        # Log end of execution
        logger.info("Finished loggertodb, " + datetime.today().isoformat())
    except Exception as e:
        logger.error(str(e))
        logger.debug(traceback.format_exc())
        raise click.ClickException(str(e))


def update_database(client, meteologger_storage):
    station_id = meteologger_storage.station_id
    ts_end_dates = {
        ts_id: client.get_ts_end_date(station_id, ts_id) or datetime(1700, 1, 1)
        for ts_id in meteologger_storage.timeseries_ids
    }
    for ts_id, ts_end_date in sorted(ts_end_dates.items(), key=lambda x: x[1]):
        new_data = meteologger_storage.get_recent_data(ts_id, ts_end_date)
        if len(new_data):
            client.post_tsdata(station_id, ts_id, HTimeseries(new_data))


if __name__ == "__main__":
    sys.exit(main())
