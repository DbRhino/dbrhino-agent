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
from . import interactive

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class _ConfigType(click.ParamType):
    name = "json_file"
    def convert(self, value, param, ctx):
        return config_.Config.from_file(value)

CONFIG_FILE = _ConfigType()
CONFIG = ("--config", "-c")
CONFIG_OPTS = dict(type=CONFIG_FILE, required=True,
                   help="Path to the configuration file")
CONFIG_PATH_OPTS = CONFIG_OPTS.copy()
CONFIG_PATH_OPTS.pop("type")


@click.command("upsert-databases")
@click.option(*CONFIG, **CONFIG_OPTS)
def upsert_databases(config):
    config.setup_logging(logger)
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


def _run_once(config):
    try:
        dbrhino = DbRhino(config)
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
    config.setup_logging(logger)
    _run_once(config)


def reload_config(config):
    try:
        new_config = config_.Config.from_file(config.filename)
        return new_config
    except:
        logger.exception("Issue reloading the config file")
        return config


def run_server(config):
    while True:
        config = reload_config(config)
        _run_once(config)
        time.sleep(config.server.interval_secs)


@click.command()
@click.option(*CONFIG, **CONFIG_OPTS)
def server(config):
    config.setup_logging(logger)
    fh = config.server.setup_logging(logger)
    runner = lambda: run_server(config)
    daemon = Daemonize(app="dbrhino_agent",
                       pid=config.server.pidfile,
                       action=runner,
                       logger=logger,
                       keep_fds=[fh.stream.fileno()])
    daemon.start()


@click.command("drop-user")
@click.option(*CONFIG, **CONFIG_OPTS)
@click.option("--database", required=True)
@click.option("--username", required=True)
def drop_user(config, database, username):
    config.setup_logging(logger)
    config.find_database(database).drop_user(username)


@click.command()
@click.pass_context
@click.option(*CONFIG, **CONFIG_PATH_OPTS)
def configure(ctx, config):
    config_path = config  # Renamed to clarify that this is just a path in this
                          # context
    try:
        interactive.configure(config_path)
    except interactive.InteractiveException:
        print("Unable to get this going.. Please contact "
              "support@dbrhino.com for assistance.")
        ctx.exit(1)


@click.command("add-database")
@click.pass_context
@click.option(*CONFIG, **CONFIG_PATH_OPTS)
def add_database(ctx, config):
    config_path = config  # Renamed to clarify that this is just a path in this
                          # context
    try:
        interactive.add_database(config_path)
    except interactive.InteractiveException:
        print("Unable to get this going.. Please contact "
              "support@dbrhino.com for assistance.")
        ctx.exit(1)


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--version", "-v", is_flag=True,
              help="Print the agent's version and exit.")
def cli(ctx, version):
    if version:
        click.echo(__version__)
        ctx.exit()
    elif not ctx.invoked_subcommand:
        ctx.fail("Missing command.")

cli.add_command(upsert_databases)
cli.add_command(run)
cli.add_command(server)
cli.add_command(drop_user)
cli.add_command(configure)
cli.add_command(add_database)
