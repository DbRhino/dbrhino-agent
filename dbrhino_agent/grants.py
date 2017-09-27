import re

IDENTIFIER_PATTERN = re.compile(r"^\w+$")


class Grant(object):
    def __init__(self, *, id, database, username, statements, version,
                 password=None, **kwargs):
        self.id = id
        self.database = database
        self.username = username
        self.statements = statements
        self.version = version
        self.password = password
