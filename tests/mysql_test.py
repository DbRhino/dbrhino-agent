# pylint: disable=attribute-defined-outside-init
from dbrhino_agent.db import mysql as my
from dbrhino_agent.db.common import first_column
import pytest


def _conf(username, password="password", schema="dbrhino_agent_tests"):
    return {
        "host": "localhost",
        "user": username,
        "password": password,
        "database": schema,
    }

MASTER_CONF = _conf("root")
HOST = "%"
TEST_USER = my.MyUname("test_user123", HOST)
TEST_PW = "PasW';drop table `foo`"
TEST_CONF = _conf(TEST_USER.username, TEST_PW)


class Base(object):
    def setup_conn(self):
        self.conn = my.connect(MASTER_CONF)
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
        if my.find_username(self.cursor, TEST_USER):
            my.drop_user(self.cursor, TEST_USER)

    def teardown(self):
        my.drop_user(self.cursor, TEST_USER)
        self.teardown_conn()

    def _grant_all(self):
        self.cursor.execute("GRANT ALL ON dbrhino_agent_tests "
                            " TO 'test_user123'@'%'")

    def test_create(self):
        my.create_user(self.cursor, TEST_USER, TEST_PW)
        self._grant_all()
        self.conn.commit()
        with my.controlled_cursor(TEST_CONF) as cur:
            cur.execute("select 1")
            assert first_column(cur) == [1]

    def test_update_pw(self):
        my.create_user(self.cursor, TEST_USER, "foobartmp")
        my.update_pw(self.cursor, TEST_USER, TEST_PW)
        self._grant_all()
        self.conn.commit()
        with my.controlled_cursor(TEST_CONF) as cur:
            cur.execute("select 1")
            assert first_column(cur) == [1]


class TestGrant(Base):
    def setup(self):
        self.setup_conn()
        my.apply_pw(self.cursor, TEST_USER, TEST_PW)
        self.x("drop schema if exists testschemaabc")
        self.x("create schema testschemaabc")
        self.x("create table testschemaabc.abc (id integer)")
        self.x("insert into testschemaabc.abc values (1), (2)")
        self.x("create table testschemaabc.def (id integer)")
        self.x("insert into testschemaabc.def values (1), (2)")
        self.conn.commit()

    def teardown(self):
        self.x("drop schema if exists testschemaabc")
        my.drop_user(self.cursor, TEST_USER)
        self.teardown_conn()

    def test_grant_and_revoke(self):
        stmts = [
            "GRANT SELECT ON testschemaabc.* TO {{username}}"
        ]
        my.apply_statements(self.cursor, TEST_USER, stmts)
        self.conn.commit()
        dsn = _conf(TEST_USER.username, TEST_PW, "testschemaabc")
        with my.controlled_cursor(dsn) as cur:
            cur.execute("select * from testschemaabc.abc")
            assert first_column(cur) == [1, 2]
        my.revoke_everything(self.cursor, TEST_USER)
        self.conn.commit()
        with pytest.raises(Exception):
            with my.controlled_cursor(dsn) as cur:
                cur.execute("select * from testschemaabc.abc")


class TestDiscovery(Base):
    def setup(self):
        self.setup_conn()

    def teardown(self):
        self.teardown_conn()

    def test_version_discovery(self):
        with my.controlled_cursor(MASTER_CONF) as cur:
            assert my.get_version(cur)
