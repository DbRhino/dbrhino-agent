import os
import json
import re
import getpass
from collections import OrderedDict
import click
from requests import HTTPError
from . import config as config_
from .dbrhino import DbRhino

BANNER = """#######################################################################
#                         Welcome to DbRhino                          #
#######################################################################"""


class InteractiveException(Exception):
    pass


def _failure(answer, checkers):
    for checker in checkers:
        resp = checker(answer)
        if resp:
            return resp
    return None


def _ask(prompt, *checkers, **kwargs):
    n_checks = 5
    for count in range(n_checks):
        answer = input(prompt).strip()
        if not answer and "default" in kwargs:
            answer = str(kwargs["default"])
        fail = _failure(answer, checkers)
        if not fail:
            return answer
        if count != (n_checks - 1):
            print(fail)
    raise InteractiveException()


def RE(ptrn, msg):
    return lambda ans: (None if re.match(ptrn, ans) else msg)

_NONEMPTY = RE(r"^.+$", "Must not be empty")
_WHATEVER = RE(r".*", "")


def configure(config_file):
    click.echo(BANNER)
    click.echo()
    conf_json = {}
    if os.path.exists(config_file):
        with open(config_file) as f:
            conf_json = json.load(fp=f, object_pairs_hook=OrderedDict)
    if not conf_json.get("access_token"):
        click.echo("You should have received a token for your agent "
                   "when you registered with DbRhino.")
        token = _ask("Enter your token here: ", _NONEMPTY)
        conf_json["access_token"] = token
    with open(config_file, "w") as f:
        json.dump(conf_json, fp=f, indent=2)
        f.write("\n")
    config = config_.Config(**conf_json)
    dbrhino = DbRhino(config)
    try:
        dbrhino.checkin()
    except HTTPError as e:
        if e.response.status_code == 401:
            click.echo("Your configured access_token does not appear to be valid."
                       " You can try again or contact support: support@dbrhino.com")
            return
        raise
    click.echo("""
Excellent! I was able to communicate with DbRhino. The next
step is to start the agent server and then add a database. Run:

    dbrhino-agent server --config {0}
    dbrhino-agent add-database --config {0}
""".format(config_file))


PORT_DEFAULTS = {
    "mysql": 3306,
    "postgresql": 5432,
    "redshift": 5439,
}
SUPERUSER_COMMANDS = {
    "mysql": [
        "-- Change `%` below if you don't want the user to connect from any IP address.",
        "CREATE USER 'dbrhino_agent'@'%' IDENTIFIED BY 'create-a-password';",
        "GRANT ALL ON *.* TO 'dbrhino_agent'@'%' WITH GRANT OPTION;",
    ],
    "postgresql": [
        "CREATE USER dbrhino_agent WITH SUPERUSER ENCRYPTED PASSWORD 'create-a-password';",
    ],
    "redshift": [
        "CREATE USER dbrhino_agent WITH CREATEUSER PASSWORD 'create-a-password';",
    ],
}


def _dbname_checker(conf_json):
    def checker(name):
        if name in conf_json.get("databases", {}):
            return "There is an existing database with that name"
        return None
    return checker


def _preamble(dbtype):
    cmds = SUPERUSER_COMMANDS[dbtype]
    click.echo("""
#######################################################################
#                       Create a Database User                        #
#######################################################################

  Below you will be asked to enter credentials for the master user.
  This user must be able to create other users and manage their grants.
  The password for this user will NEVER be sent to DbRhino.

  To create this user, you must run the below command{}. You can change
  the username if you'd like and you should choose your own password.
""".format("s" if len(cmds) > 1 else ""))
    for c in SUPERUSER_COMMANDS[dbtype]:
        click.echo("  " + c)
    click.echo()
    input("Press enter when you have a user ready.")


def _build_dbconf(dbtype):
    host = _ask("Host: ", _NONEMPTY)
    port_prompt = "Port (default {}): ".format(PORT_DEFAULTS[dbtype])
    port = _ask(port_prompt, RE(r"^[0-9]*$", "Must be numeric"),
                default=PORT_DEFAULTS[dbtype])
    db_required = (dbtype != "mysql")
    db_prompt = "Database{}: ".format("" if db_required else " (optional)")
    db_checker = (_NONEMPTY if db_required else _WHATEVER)
    database = _ask(db_prompt, db_checker)
    user = _ask("User: ", _NONEMPTY)
    password = getpass.getpass()
    dbconf = {
        "type": dbtype,
        "host": host,
        "port": port,
        "user": user,
        "password": password,
    }
    if database:
        dbconf["database"] = database
    return dbconf


def add_database(config_file):
    if not os.path.exists(config_file):
        click.echo("The config file does not exist")
        return
    with open(config_file) as f:
        conf_json = json.load(fp=f, object_pairs_hook=OrderedDict)
    dbtype = _ask(
        "Database type (postgresql, redshift, or mysql): ",
        RE(r"^(postgresql|redshift|mysql)$",
           "Must be one of: postgresql, redshift, mysql")
    )
    _preamble(dbtype)
    click.echo("""
#######################################################################
#                          Database Details                           #
#######################################################################

  You will first be asked for a name. This name must be unique; it is
  used to identity the database within DbRhino. Note that you will not
  be able to change this name later.
""")
    name = _ask("Name: ", _NONEMPTY, _dbname_checker(conf_json))
    dbconf = _build_dbconf(dbtype)
    if "databases" not in conf_json:
        conf_json["databases"] = {}
    conf_json["databases"][name] = dbconf
    with open(config_file, "w") as f:
        json.dump(conf_json, fp=f, indent=2)
        f.write("\n")
    click.echo("""
#######################################################################
#                          Test and Register                          #
#######################################################################

  We will now test connection to this database and if all goes well,
  register it in DbRhino.
""")
    input("Press enter to proceed.")
    try:
        config = config_.Config(**conf_json)
        dbrhino = DbRhino(config)
        dbrhino.upsert_databases(only=name)
    except:
        raise
    click.echo("""
    Success! Your database is ready to go.""")
