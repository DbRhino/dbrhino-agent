import re
import logging
import pymysql as mysql
from pymysql.converters import escape_str
from . import common
from ..dbrhino import GrantResult
from .. import templates as tmpl

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
        sqls = tmpl.render_and_split(
            stmt,
            username=str(my_uname),
        )
        for sql in sqls:
            cur.execute(sql)


def revoke_everything(cur, my_uname):
    cur.execute("REVOKE ALL PRIVILEGES, GRANT OPTION FROM {}"
                .format(my_uname))


def connect(dbconf):
    driver_keys = ["host", "port", "database", "user", "password"]
    driver_conf = {k: dbconf[k] for k in driver_keys if k in dbconf}
    return mysql.connect(**driver_conf)


class controlled_cursor(object):
    def __init__(self, dbconf):
        self.dbconf = dbconf
        self._conn = None
        self._cursor = None

    def __enter__(self):
        self._conn = connect(self.dbconf)
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
        logger.info("implementing grant for %s in %s",
                    grant.username, self.name)
        with controlled_cursor(self.dbconf) as cur:
            my_uname = MyUname(grant.username, HOST)
            if grant.password:
                apply_pw(cur, my_uname, grant.password)
            elif not find_username(cur, my_uname):
                return GrantResult.NO_PASSWORD
            revoke_everything(cur, my_uname)
            apply_statements(cur, my_uname, grant.statements)
            return GrantResult.APPLIED

    def drop_user(self, username):
        with controlled_cursor(self.dbconf) as cur:
            if find_username(cur, username):
                logger.info("dropping user %s from %s", username, self.name)
                drop_user(cur, username)
                return GrantResult.REVOKED
            return GrantResult.NO_CHANGE

    def discover_dbversion(self):
        with controlled_cursor(self.dbconf) as cur:
            return get_version(cur)
