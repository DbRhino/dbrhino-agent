#!/usr/bin/env python3
import json
import logging
import time
import click
from . import config as config_
from .dbrhino import DbRhino, Grant, GrantResult
from ._version import __version__

logging.basicConfig()
root_logger = logging.getLogger("")
root_logger.level = logging.INFO
logging.getLogger("dbrhino_agent").level = logging.DEBUG
logger = logging.getLogger(__name__)


class _ConfigType(click.ParamType):
    name = "json_file"

    def convert(self, value, param, ctx):
        return config_.Config.from_file(value)

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
def server(config, interval_secs):
    dbrhino = DbRhino(config)
    while True:
        _run_once(dbrhino)
        time.sleep(interval_secs)


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
