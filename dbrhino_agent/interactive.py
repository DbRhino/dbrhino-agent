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
    if not os.path.exists(config_file):
        print("You should have received a token for your agent "
              "when you registered with DbRhino.")
        token = input("Enter your token here: ")
        config = {
            "access_token": token,
        }
        with open(config_file, "w") as f:
            json.dump(config, fp=f, indent=2)
            f.write("\n")
    config = config_.Config.from_file(config_file)
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


def add_database(config_file):
    if not os.path.exists(config_file):
        print("The config file does not exist")
        return FAILURE
    with open(config_file) as f:
        conf_json = json.load(fp=f, object_pairs_hook=OrderedDict)
    print("It is recommended you backup {} before proceeding.".format(config_file))
    input("Press enter if you wish to continue.")
    try:
        name = _get_a_name(conf_json)
        dbtype = _ask_until_matches("Database type (postgresql, redshift, or mysql): ",
                                    r"^(postgresql|redshift|mysql)$",
                                    "Must be one of: postgresql, redshift, mysql")
        host = _ask_until_matches("Host: ", *_NONEMPTY)
        port_prompt = "Port (default {}): ".format(PORT_DEFAULTS[dbtype])
        port = _ask_until_matches(port_prompt, r"^[0-9]*$", "Must be numeric")
        db_required = (dbtype != "mysql")
        db_prompt = "Database{}: ".format("" if db_required else " (optional)")
        db_args = (_NONEMPTY if db_required else _WHATEVER)
        database = _ask_until_matches(db_prompt, *db_args)
        print("\nNow you will be asked to enter credentials for the master user.")
        print("This user must be able to create other users and manage their grants.")
        print("The password for this user will NEVER be sent to DbRhino.")
        user = _ask_until_matches("User: ", *_NONEMPTY)
        password = getpass.getpass()
    except InteractiveException as e:
        print("Unable to get this going.. Please contact "
              "support@dbrhino.com for assistance.")
        return FAILURE
    dbconf = {
        "type": dbtype,
        "host": host,
        "port": int(port or PORT_DEFAULTS[dbtype]),
        "user": user,
        "password": password,
    }
    if database:
        dbconf["database"] = database
    if "databases" not in conf_json:
        conf_json["databases"] = {}
    conf_json["databases"][name] = dbconf
    with open(config_file, "w") as f:
        json.dump(conf_json, fp=f, indent=2)
        f.write("\n")
    print("Your new configuration has been saved.")
    input("We will now register this database in DbRhino. Press enter to proceed.")
    config = config_.Config(**conf_json)
    dbrhino = DbRhino(config)
    dbrhino.upsert_databases(only=name)
