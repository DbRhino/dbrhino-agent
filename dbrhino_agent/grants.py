import re

IDENTIFIER_PATTERN = re.compile(r"^\w+$")


class Policy(object):
    def __init__(self, *, statements, **kwargs):
        self.statements = statements


class Grant(object):
    def __init__(self, *, id, database, username, policy, version,
                 password=None, **kwargs):
        self.id = id
        self.database = database
        self.username = username
        self.policy = Policy(**policy)
        self.version = version
        self.password = password
