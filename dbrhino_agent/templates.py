import sqlparse
from jinja2 import Environment

env = Environment()
env.filters.clear()
env.globals.clear()


def render(stmt, **kwargs):
    return env.from_string(stmt).render(**kwargs)


def split(sql):
    """Takes a string containing sql statements and comments and returns
    just the sql statements as a list."""
    return sqlparse.split(sqlparse.format(sql.strip(), strip_comments=True))


def render_and_split(stmt, **kwargs):
    str_ = render(stmt, **kwargs)
    return split(str_)
