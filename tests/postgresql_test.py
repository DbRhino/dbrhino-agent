# pylint: disable=attribute-defined-outside-init
from dbrhino_agent.db import postgresql as pg
from dbrhino_agent.db.utils import first_column
import pytest


def _dsn(username, password="password"):
    return ("postgresql://{}:{}@localhost/dbrhino_agent_tests"
            .format(username, password))

MASTER_DSN = _dsn(username="buck")
TEST_USER = "test_user123"
TEST_PW = "PasW';drop table `foo`"
TEST_DSN = _dsn(TEST_USER, TEST_PW)


class Base(object):
    def setup_conn(self):
        self.conn = pg.connect(MASTER_DSN)
        self.cursor = self.conn.cursor()

    def teardown_conn(self):
        self.conn.commit()
        self.cursor.close()
        self.conn.close()

    def x(self, *args, **kwargs):
        self.cursor.execute(*args, **kwargs)


class TestUsers(Base):
    def setup(self):
        self.setup_conn()
        if pg.find_username(self.cursor, TEST_USER):
            pg.drop_user(self.cursor, TEST_USER)

    def teardown(self):
        pg.drop_user(self.cursor, TEST_USER)
        self.teardown_conn()

    def test_create(self):
        pg.create_user(self.cursor, TEST_USER, TEST_PW)
        self.conn.commit()
        with pg.controlled_cursor(TEST_DSN) as cur:
            cur.execute("select 1")
            assert first_column(cur) == [1]

    def test_update_pw(self):
        pg.create_user(self.cursor, TEST_USER, "foobartmp")
        pg.update_pw(self.cursor, TEST_USER, TEST_PW)
        self.conn.commit()
        with pg.controlled_cursor(TEST_DSN) as cur:
            cur.execute("select 1")
            assert first_column(cur) == [1]


class TestOps(Base):
    def setup(self):
        self.setup_conn()
        pg.apply_pw(self.cursor, TEST_USER, TEST_PW)
        self.x("drop schema if exists testschemaabc cascade")
        self.x("create schema testschemaabc")
        self.x("create table testschemaabc.abc (x integer, y text)")
        self.x("insert into testschemaabc.abc values (1, 'a'), (2, 'b')")
        self.x("create table testschemaabc.def (x integer)")
        self.x("insert into testschemaabc.def values (1), (2)")
        self.conn.commit()
        self.catalog = pg.Catalog.discover(self.cursor)

    def teardown(self):
        self.x("drop schema if exists testschemaabc cascade")
        pg.drop_user(self.cursor, TEST_USER)
        self.teardown_conn()

    def test_grant_and_revoke(self):
        stmts = [
            "GRANT USAGE ON SCHEMA testschemaabc TO {{username}}",
            "GRANT SELECT ON ALL TABLES IN SCHEMA testschemaabc TO {{username}}",
        ]
        pg.apply_statements(self.cursor, self.catalog, TEST_USER, stmts)
        self.conn.commit()
        with pg.controlled_cursor(TEST_DSN) as cur:
            cur.execute("select * from testschemaabc.abc")
            assert first_column(cur) == [1, 2]
        pg.revoke_everything(self.cursor, self.catalog, TEST_USER)
        self.conn.commit()
        with pg.controlled_cursor(TEST_DSN) as cur:
            with pytest.raises(Exception):
                cur.execute("select * from testschemaabc.abc")

    def test_database_grant(self):
        stmts = [
            "GRANT CONNECT ON DATABASE {{database}} TO {{username}}"
        ]
        pg.apply_statements(self.cursor, self.catalog, TEST_USER, stmts)
        self.conn.commit()
        with pg.controlled_cursor(TEST_DSN) as cur:
            cur.execute("select 1")
            assert first_column(cur) == [1]
        pg.revoke_everything(self.cursor, self.catalog, TEST_USER)
        self.conn.commit()

    def test_column_level_grant(self):
        stmts = [
            "GRANT USAGE ON SCHEMA testschemaabc TO {{username}}",
            "GRANT SELECT (x), INSERT (x) ON TABLE testschemaabc.abc TO {{username}}"
        ]
        pg.apply_statements(self.cursor, self.catalog, TEST_USER, stmts)
        self.conn.commit()
        with pg.controlled_cursor(TEST_DSN) as cur:
            cur.execute("select x from testschemaabc.abc")
            assert first_column(cur) == [1, 2]
            with pytest.raises(Exception):
                cur.execute("select y from testschemaabc.abc")
        pg.revoke_everything(self.cursor, self.catalog, TEST_USER)
        self.conn.commit()
        with pg.controlled_cursor(TEST_DSN) as cur:
            with pytest.raises(Exception):
                cur.execute("select x from testschemaabc.abc")

    def test_granting_all_schemas(self):
        stmts = ["""
        {% for schema in all_schemas %}
        GRANT USAGE ON SCHEMA {{schema}} TO {{username}};
        GRANT SELECT ON ALL TABLES IN SCHEMA {{schema}} TO {{username}};
        {% endfor %}
         """]
        pg.apply_statements(self.cursor, self.catalog, TEST_USER, stmts)
        self.conn.commit()
        with pg.controlled_cursor(TEST_DSN) as cur:
            cur.execute("select * from testschemaabc.abc")
            assert first_column(cur) == [1, 2]
        pg.revoke_everything(self.cursor, self.catalog, TEST_USER)
        self.conn.commit()
        with pg.controlled_cursor(TEST_DSN) as cur:
            with pytest.raises(Exception):
                cur.execute("select * from testschemaabc.abc")


class TestDiscovery(Base):
    def setup(self):
        self.setup_conn()

    def teardown(self):
        self.teardown_conn()

    def test_version_discovery(self):
        with pg.controlled_cursor(MASTER_DSN) as cur:
            assert pg.get_pg_version(cur)
