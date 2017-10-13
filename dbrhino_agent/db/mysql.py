import re
import logging
from urllib.parse import urlparse
import pymysql as mysql
from pymysql.converters import escape_str
import jinja2
from . import common
from ..dbrhino import GrantResult

logger = logging.getLogger(__name__)


def get_version(cur):
    cur.execute("select version()")
    ver_string = common.scalar_result(cur)
    match = re.match(r"([0-9.]+)-", ver_string)
    return match.group(1) if match else None


class MyUname(object):
    def __init__(self, username, host):
        self.username = username
        self.host = host

    def __str__(self):
        return "{}@{}".format(escape_str(self.username),
                              escape_str(self.host))


def find_username(cur, my_uname):
    cur.execute(
        "SELECT user, host FROM mysql.user WHERE user = %s AND host = %s",
        (my_uname.username, my_uname.host,)
    )
    return cur.fetchone()


def create_user(cur, my_uname, pw):
    cur.execute("CREATE USER {} IDENTIFIED BY {}"
                .format(my_uname, escape_str(pw)))


def drop_user(cur, my_uname):
    cur.execute("DROP USER {}".format(my_uname))


def update_pw(cur, my_uname, pw):
    cur.execute("SET PASSWORD FOR {} = {}"
                .format(my_uname, escape_str(pw)))


def apply_pw(cur, my_uname, pw):
    if find_username(cur, my_uname):
        update_pw(cur, my_uname, pw)
    else:
        create_user(cur, my_uname, pw)


def apply_statements(cur, my_uname, statements):
    for stmt in statements:
        templ = jinja2.Template(stmt)
        sql = templ.render(username=str(my_uname))
        cur.execute(sql)


def revoke_everything(cur, my_uname):
    cur.execute("REVOKE ALL PRIVILEGES, GRANT OPTION FROM {}"
                .format(my_uname))


def connect(connect_opt):
    parsed_url = urlparse(connect_opt) \
        if isinstance(connect_opt, str) else connect_opt
    kw = {}
    for opt, attr in (("host", "hostname"),
                      ("port", "port"),
                      ("user", "username"),
                      ("passwd", "password")):
        val = getattr(parsed_url, attr)
        if val:
            kw[opt] = val
    if parsed_url.path:
        kw["db"] = parsed_url.path[1:]
    return mysql.connect(**kw)


class controlled_cursor(object):
    def __init__(self, connect_opt):
        self.connect_opt = connect_opt
        self._conn = None
        self._cursor = None

    def __enter__(self):
        self._conn = connect(self.connect_opt)
        self._cursor = self._conn.cursor()
        return self._cursor

    def __exit__(self, exception_type, exception_value, traceback):
        if not exception_type:
            self._conn.commit()
        self._cursor.close()
        self._conn.close()


HOST = "%"  # Will eventually have to make this configurable

class MySQL(common.Database):
    def implement_grant(self, grant):
        logger.debug("implementing grant for %s in %s",
                     grant.username, self.name)
        with controlled_cursor(self.parsed_url) as cur:
            my_uname = MyUname(grant.username, HOST)
            if grant.password:
                apply_pw(cur, my_uname, grant.password)
            elif not find_username(cur, my_uname):
                return GrantResult.NO_PASSWORD
            revoke_everything(cur, my_uname)
            apply_statements(cur, my_uname, grant.statements)
            return GrantResult.APPLIED

    def drop_user(self, username):
        with controlled_cursor(self.parsed_url) as cur:
            if find_username(cur, username):
                drop_user(cur, username)
                return GrantResult.REVOKED
            return GrantResult.NO_CHANGE

    # pylint: disable=no-self-use
    def discover_dbtype(self):
        return "mysql"

    def discover_dbversion(self):
        with controlled_cursor(self.connect_to) as cur:
            return get_version(cur)
