import os
import sys
import json
import logging
from . import db

SERVER_URL = "https://app.dbrhino.com"
LOG_FMT = logging.Formatter(
    "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s")


class UnknownDbException(Exception):
    pass


class ServerConfig(object):
    def __init__(self, *, pidfile="dbrhino.pid", logfile="dbrhino.log"):
        self.pidfile = pidfile
        self.logfile = logfile
        self.interval_secs = 30

    def setup_logging(self, logger):
        fh = logging.FileHandler(self.logfile, "a")
        fh.setFormatter(LOG_FMT)
        logger.addHandler(fh)
        return fh


class Config(object):
    def __init__(self, *, access_token, server_url=SERVER_URL, databases={},
                 debug=False, server=None, filename=None, **kwargs):
        self.access_token = access_token
        self.server_url = server_url
        self.debug = debug
        self.databases = {
            name: db.create(name=name, **conf)
            for name, conf in databases.items()
        }
        self.filename = filename
        self.server = ServerConfig(**(server or {}))

    @classmethod
    def from_file(cls, filename):
        fpath = os.path.abspath(filename)
        with open(fpath) as f:
            return cls(filename=fpath, **json.loads(f.read()))

    def find_database(self, name):
        if name not in self.databases:
            raise UnknownDbException(name)
        return self.databases[name]

    def setup_logging(self, logger):
        if self.debug:
            logger.setLevel(logging.DEBUG)
            sh = logging.StreamHandler(sys.stdout)
            sh.setFormatter(LOG_FMT)
            logger.addHandler(sh)
