import json
import collections
from . import db

SERVER_URL = "https://app.dbrhino.com"


class UnknownDbException(Exception):
    pass


class Config(object):
    def __init__(self, *, access_token, server_url=SERVER_URL, databases={},
                 debug=False, filename=None, **kwargs):
        self.access_token = access_token
        self.server_url = server_url
        self.debug = debug
        self.databases = {
            name: db.create(name=name, **conf)
            for name, conf in databases.items()
        }
        self.filename = filename

    @classmethod
    def from_file(cls, filename):
        with open(filename) as f:
            return cls(filename=filename, **json.loads(f.read()))

    def find_database(self, name):
        if name not in self.databases:
            raise UnknownDbException(name)
        return self.databases[name]
