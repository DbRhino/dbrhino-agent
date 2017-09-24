#!/usr/bin/env python3
import click
from .click_utils import CONFIG, CONFIG_OPTS
from .dbrhino import DbRhino
from .grants import Grant
from .db import NoPasswordException
import logging
from requests.exceptions import ConnectionError
import time
from .__version__ import __version__

logging.basicConfig()
root_logger = logging.getLogger("")
root_logger.level = logging.INFO
logging.getLogger("dbrhino_agent").level = logging.DEBUG
logger = logging.getLogger(__name__)


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
            applied = {"id": grant.id, "version": grant.version}
        except:
            logger.exception("grant definition is malformed!!!")
            continue
        try:
            db = dbrhino.config.find_database(grant.database)
            db.implement_grant(grant)
            applied["result"] = "success"
        except NoPasswordException as e:
            applied["result"] = "no_user_password"
            logger.info(e.args[0])
        except:
            applied["result"] = "unknown_error"
            logger.exception("Unknown error implementing grant")
        applied_grants.append(applied)
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
