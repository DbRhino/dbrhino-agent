#!/usr/bin/env python3
import sys
import json
import logging
import time
import click
from daemonize import Daemonize
from . import config as config_
from .dbrhino import DbRhino, Grant, GrantResult
from .version import __version__

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
fmt = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s")


class _ConfigType(click.ParamType):
    name = "json_file"
    def convert(self, value, param, ctx):
        config = config_.Config.from_file(value)
        if config.debug:
            logger.setLevel(logging.DEBUG)
            sh = logging.StreamHandler(sys.stdout)
            sh.setFormatter(fmt)
            logger.addHandler(sh)
        return config

_JSON_FILE = _ConfigType()
CONFIG = ("--config", "-c")
CONFIG_OPTS = dict(type=_JSON_FILE, required=True)


@click.command("upsert-databases")
@click.option(*CONFIG, **CONFIG_OPTS)
def upsert_databases(config):
    DbRhino(config).upsert_databases()


def _fetch_and_apply_grants(dbrhino):
    grant_defs = dbrhino.fetch_grants()["grants"]
    applied_grants = []
    for grant_def in grant_defs:
        try:
            grant = Grant(**grant_def)
        except:
            logger.exception("grant definition is malformed!!!")
            continue
        try:
            db = dbrhino.config.find_database(grant.database)
            result = db.drop_user(grant.username) \
                if grant.revoke else db.implement_grant(grant)
        except config_.UnknownDbException:
            result = GrantResult.UNKNOWN_DATABASE
        except:
            logger.exception("Unknown error implementing grant")
            result = GrantResult.UNKNOWN_ERROR
        if result != GrantResult.NO_CHANGE:
            applied_grants.append({"id": grant.id,
                                   "version": grant.version,
                                   "result": result})
    dbrhino.checkin(applied_grants)


def _run_once(dbrhino):
    try:
        dbrhino.upsert_databases()
    except:
        logger.exception("Error while upserting databases")
    try:
        _fetch_and_apply_grants(dbrhino)
    except:
        logger.exception("Error while applying grants")


@click.command()
@click.option(*CONFIG, **CONFIG_OPTS)
def run(config):
    _run_once(DbRhino(config))


@click.command()
@click.option(*CONFIG, **CONFIG_OPTS)
@click.option("--interval-secs", type=click.INT, default=30)
@click.option("--pidfile", required=True)
@click.option("--logfile", required=True)
def server(config, interval_secs, pidfile, logfile):
    fh = logging.FileHandler(logfile, "a")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    def run_server():
        dbrhino = DbRhino(config)
        while True:
            _run_once(dbrhino)
            time.sleep(interval_secs)
    daemon = Daemonize(app="dbrhino_agent", pid=pidfile, action=run_server,
                       logger=logger, keep_fds=[fh.stream.fileno()])
    daemon.start()


@click.command("drop-user")
@click.option(*CONFIG, **CONFIG_OPTS)
@click.option("--database", required=True)
@click.option("--username", required=True)
def drop_user(config, database, username):
    config.find_database(database).drop_user(username)


@click.command()
def version():
    print(__version__)


@click.group()
def cli():
    pass

cli.add_command(upsert_databases)
cli.add_command(run)
cli.add_command(server)
cli.add_command(drop_user)
cli.add_command(version)
