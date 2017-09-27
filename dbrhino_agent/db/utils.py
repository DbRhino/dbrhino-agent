class Database(object):
    def __init__(self, *, name, connect_to, parsed_url, **kwargs):
        self.name = name
        self.connect_to = connect_to
        self.parsed_url = parsed_url


class GrantPermission(object):
    NONE = "none"
    SELECT = "select"


def first_column(cur):
    return [x for x, *_ in cur.fetchall()]


def scalar_result(cur):
    col = first_column(cur)
    return col[0] if col else None
