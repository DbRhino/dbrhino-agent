class Database(object):
    def __init__(self, name, dbconf):
        self.name = name
        self.dbconf = dbconf
        self.dbtype = dbconf["type"]


def first_column(cur):
    return [x for x, *_ in cur.fetchall()]


def scalar_result(cur):
    col = first_column(cur)
    return col[0] if col else None
