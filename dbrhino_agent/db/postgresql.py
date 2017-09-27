import logging
import psycopg2
from psycopg2.extras import quote_ident
import jinja2
from .utils import Database, first_column, scalar_result
import re
from ..dbrhino import GrantResult

logger = logging.getLogger(__name__)


def get_full_version(cur):
    cur.execute("select version()")
    return scalar_result(cur)


def get_pg_version(cur):
    match = re.search(r"PostgreSQL\s+([0-9.]+)")
    get_full_version(cur)


def is_redshift(cur):
    return "redshift" in get_full_version(cur).lower()


def current_database(cur):
    cur.execute("SELECT current_database()")
    return scalar_result(cur)


def discover_all_schemas(cur):
    cur.execute("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT LIKE 'pg_%'
        AND schema_name != 'information_schema'
    """)
    return first_column(cur)


class Catalog(object):
    def __init__(self, *, database, schemas):
        self.database = database
        self.schemas = schemas

    @classmethod
    def discover(cls, cur):
        return cls(
            database=current_database(cur),
            schemas=discover_all_schemas(cur),
        )


def find_username(cur, username):
    cur.execute(
        "SELECT usename FROM pg_catalog.pg_user WHERE usename = %s",
        (username,)
    )
    return scalar_result(cur)


def create_user(cur, username, pw):
    if is_redshift(cur):
        cur.execute("CREATE USER {} PASSWORD %s"
                    .format(quote_ident(username, cur)),
                    (pw,))
    else:
        cur.execute("CREATE USER {} WITH ENCRYPTED PASSWORD %s"
                    .format(quote_ident(username, cur)),
                    (pw,))


def drop_user(cur, username):
    cur.execute("DROP ROLE {}".format(quote_ident(username, cur)))


def update_pw(cur, username, pw):
    cur.execute("ALTER ROLE {} WITH ENCRYPTED PASSWORD %s"
                .format(quote_ident(username, cur)),
                (pw,))


def apply_pw(cur, username, pw):
    if find_username(cur, username):
        update_pw(cur, username, pw)
    else:
        create_user(cur, username, pw)


def revoke_everything(cur, catalog, username):
    cur.execute("REVOKE ALL ON DATABASE {} FROM {}"
                .format(quote_ident(catalog.database, cur),
                        quote_ident(username, cur)))
    schema_sqls = [
        "REVOKE ALL ON SCHEMA {} FROM {}",
        "REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}",
        "REVOKE ALL ON ALL SEQUENCES IN SCHEMA {} FROM {}",
        "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {} FROM {}",
    ]
    for schema in catalog.schemas:
        for sql in schema_sqls:
            cur.execute(sql.format(quote_ident(schema, cur),
                                   quote_ident(username, cur)))


def apply_statements(cur, catalog, username, statements):
    for stmt in statements:
        templ = jinja2.Template(stmt)
        sql = templ.render(database=quote_ident(catalog.database, cur),
                           username=quote_ident(username, cur))
        cur.execute(sql)


def connect(connect_to):
    return psycopg2.connect(connect_to)


class controlled_cursor(object):
    def __init__(self, connect_to):
        self.connect_to = connect_to
        self._conn = None
        self._cursor = None

    def __enter__(self):
        self._conn = connect(self.connect_to)
        self._cursor = self._conn.cursor()
        return self._cursor

    def __exit__(self, exception_type, exception_value, traceback):
        if not exception_type:
            self._conn.commit()
        self._cursor.close()
        self._conn.close()


class Postgresql(Database):
    def implement_grant(self, grant):
        logger.debug("implementing grant for %s in %s",
                     grant.username, self.name)
        with controlled_cursor(self.connect_to) as cur:
            if grant.password:
                apply_pw(cur, grant.username, grant.password)
            elif not find_username(cur, grant.username):
                return GrantResult.NO_PASSWORD
            catalog = Catalog.discover(cur)
            revoke_everything(cur, catalog, grant.username)
            apply_statements(cur, catalog, grant.username,
                             grant.statements)
            return GrantResult.APPLIED

    def drop_user(self, username):
        logger.info("dropping user %s from %s", username, self.name)
        with controlled_cursor(self.connect_to) as cur:
            if not find_username(cur, username):
                return GrantResult.NO_CHANGE
            catalog = Catalog.discover(cur)
            revoke_everything(cur, catalog, username)
            cur.connection.commit()
            drop_user(cur, username)
            return GrantResult.REVOKED

    @property
    def dbtype(self):
        with controlled_cursor(self.connect_to) as cur:
            if is_redshift(cur):
                return "redshift"
            return "postgresql"
