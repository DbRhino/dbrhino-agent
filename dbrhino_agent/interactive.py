import os
import json
import re
import getpass
from collections import OrderedDict
from requests import HTTPError
from . import config as config_
from .dbrhino import DbRhino

BANNER = """#######################################################################
#                         Welcome to DbRhino                          #
#######################################################################

This interactive setup will get your agent up and running."""

SUCCESS = 0
FAILURE = 1


def configure(config_file):
    print(BANNER)
    print()
    conf_json = {}
    if os.path.exists(config_file):
        with open(config_file) as f:
            conf_json = json.load(fp=f, object_pairs_hook=OrderedDict)
    if not conf_json.get("access_token"):
        print("You should have received a token for your agent "
              "when you registered with DbRhino.")
        token = input("Enter your token here: ").strip()
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
            print("Your configured access_token does not appear to be valid."
                  " You can try again or contact support: support@dbrhino.com")
            return FAILURE
        raise
    print("Excellent! I was able to communicate with DbRhino.")
    print("Please head back to the DbRhino app for next steps.")
    return SUCCESS


class InteractiveException(Exception):
    pass


def _ask_until_matches(prompt, ptrn, extra_help=""):
    for count in range(5):
        if count > 0 and extra_help:
            print(extra_help)
        answer = input(prompt)
        if re.match(ptrn, answer):
            return answer
    raise InteractiveException()

_NONEMPTY = (r"^.+$", "Must not be empty")
_WHATEVER = (r".*", "")
PORT_DEFAULTS = {
    "mysql": 3306,
    "postgresql": 5432,
    "redshift": 5439,
}
SUPERUSER_COMMANDS = {
    "mysql": [
        "-- Change `%` below if you don't want the user to connect from any IP address.",
        "CREATE USER 'dbrhino_master'@'%' IDENTIFIED BY 'create-a-password';",
        "GRANT ALL ON *.* TO 'dbrhino_master'@'%' WITH GRANT OPTION;",
    ],
    "postgresql": [
        "CREATE USER dbrhino_master WITH SUPERUSER ENCRYPTED PASSWORD 'create-a-password';",
    ],
    "redshift": [
        "CREATE USER dbrhino_master WITH CREATEUSER PASSWORD 'create-a-password';",
    ],
}


def _get_a_name(conf_json):
    prompt = "Give your database a unique name. You will NOT be able to change this: "
    for count in range(5):
        name = input(prompt)
        if not name:
            print("Name must not be empty")
        elif name in conf_json.get("databases", {}):
            print("There is an existing database with that name")
        else:
            return name
    raise InteractiveException()


def _preamble(dbtype):
    cmds = SUPERUSER_COMMANDS[dbtype]
    print("""
Below you will be asked to enter credentials for the master user.
This user must be able to create other users and manage their grants.
The password for this user will NEVER be sent to DbRhino.

To create this user, you must run the below command{}. You can change the
username if you'd like and you should choose your own password.
""".format("s" if len(cmds) > 1 else ""))
    for c in SUPERUSER_COMMANDS[dbtype]:
        print("  " + c)
    print()
    input("Press enter when you are ready to continue.")


def _build_dbconf(dbtype):
    host = _ask_until_matches("Host: ", *_NONEMPTY)
    port_prompt = "Port (default {}): ".format(PORT_DEFAULTS[dbtype])
    port = _ask_until_matches(port_prompt, r"^[0-9]*$", "Must be numeric")
    db_required = (dbtype != "mysql")
    db_prompt = "Database{}: ".format("" if db_required else " (optional)")
    db_args = (_NONEMPTY if db_required else _WHATEVER)
    database = _ask_until_matches(db_prompt, *db_args)
    user = _ask_until_matches("User: ", *_NONEMPTY)
    password = getpass.getpass()
    dbconf = {
        "type": dbtype,
        "host": host,
        "port": int(port or PORT_DEFAULTS[dbtype]),
        "user": user,
        "password": password,
    }
    if database:
        dbconf["database"] = database
    return dbconf


def add_database(config_file):
    if not os.path.exists(config_file):
        print("The config file does not exist")
        return FAILURE
    with open(config_file) as f:
        conf_json = json.load(fp=f, object_pairs_hook=OrderedDict)
    try:
        dbtype = _ask_until_matches(
            "Database type (postgresql, redshift, or mysql): ",
            r"^(postgresql|redshift|mysql)$",
            "Must be one of: postgresql, redshift, mysql",
        )
        _preamble(dbtype)
        name = _get_a_name(conf_json)
        dbconf = _build_dbconf(dbtype)
    except InteractiveException as e:
        print("Unable to get this going.. Please contact "
              "support@dbrhino.com for assistance.")
        return FAILURE
    if "databases" not in conf_json:
        conf_json["databases"] = {}
    conf_json["databases"][name] = dbconf
    with open(config_file, "w") as f:
        json.dump(conf_json, fp=f, indent=2)
        f.write("\n")
    print("Your new configuration has been saved.")
    input("We will now test connection to this database and register it"
          " in DbRhino. Press enter to proceed.")
    config = config_.Config(**conf_json)
    dbrhino = DbRhino(config)
    dbrhino.upsert_databases(only=name)
