package main

import (
	"database/sql"
	"log"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/suite"
)

type PostgresqlTestSuite struct {
	suite.Suite
	App *Application
}

const PG_URI_MASTER = "postgres://buck:password@localhost:5432/dbrhino_agent_tests?sslmode=disable"
const PG_URI_TESTER = "postgres://testUser123:foobar1234@localhost:5432/dbrhino_agent_tests?sslmode=disable"

func withPostgresqlTestConnection(uri string, f func(*sql.DB)) {
	DB, err := sql.Open("postgres", uri)
	if err != nil {
		log.Fatalf("Error opening test database %s", err)
	}
	defer DB.Close()
	f(DB)
}

func postgresqlTestGrantResponse(statements []string) *GrantsResponse {
	return &GrantsResponse{
		Connections: []Connection{
			Connection{
				Id: 1,
				Database: &Database{
					Id:                1,
					Name:              "pg_test",
					Type:              "postgresql",
					Host:              "localhost",
					Port:              5432,
					Username:          "buck",
					DecryptedPassword: "password",
					DefaultDatabase:   "dbrhino_agent_tests",
				},
				DbName: "dbrhino_agent_tests",
			},
		},
		Users: []User{
			User{
				Id:                1,
				DecryptedPassword: "foobar1234",
				Active:            true,
				Username:          "testUser123",
				DatabaseId:        1,
			},
		},
		Grants: []Grant{
			Grant{
				Id:           1,
				DatabaseId:   1,
				ConnectionId: 1,
				UserId:       1,
				Statements:   statements,
				Version:      "abc",
				Username:     "testUser123",
			},
		},
	}
}

func execShouldPass(t *testing.T, DB *sql.DB, sql string) *sql.Result {
	res, err := DB.Exec(sql)
	assert.Nil(t, err)
	return &res
}

func (suite *PostgresqlTestSuite) SetupTest() {
	conf := &Config{}
	app := &Application{conf, nil}
	suite.App = app
	withPostgresqlTestConnection(PG_URI_MASTER, func(DB *sql.DB) {
		DB.Exec("drop role testUser123")
		tx, err := DB.Begin()
		assert.Nil(suite.T(), err)
		execShouldPass(suite.T(), DB, "drop schema if exists test_schema cascade")
		execShouldPass(suite.T(), DB, "create schema test_schema")
		execShouldPass(suite.T(), DB, "create table test_schema.abc (x integer, y text)")
		execShouldPass(suite.T(), DB, "insert into test_schema.abc values (1, 'a'), (2, 'b')")
		execShouldPass(suite.T(), DB, "create table test_schema.def (x integer)")
		execShouldPass(suite.T(), DB, "insert into test_schema.def values (1), (2)")
		assert.Nil(suite.T(), tx.Commit())
	})
}

func (suite *PostgresqlTestSuite) TestBasicGrant() {
	grantsResponse := postgresqlTestGrantResponse([]string{
		"GRANT USAGE ON SCHEMA test_schema TO {{username}}",
		"GRANT SELECT ON ALL TABLES IN SCHEMA test_schema TO {{username}}",
	})
	checkin := handleGrantsResponse(suite.App, grantsResponse)
	t := suite.T()
	assert.Len(t, checkin.UserResults, 1)
	assert.Len(t, checkin.GrantResults, 1)
	userResult := checkin.UserResults[0]
	assert.Equal(t, userResult.UserId, 1)
	assert.Equal(t, userResult.Result, RESULT_APPLIED)
	assert.Nil(t, userResult.Error)
	grantResult := checkin.GrantResults[0]
	assert.Equal(t, grantResult.GrantId, 1)
	assert.Equal(t, grantResult.Result, RESULT_APPLIED)
	assert.Nil(t, grantResult.Error)
	withPostgresqlTestConnection(PG_URI_TESTER, func(DB *sql.DB) {
		execShouldPass(t, DB, "select * from test_schema.abc")
	})
}

func TestPostgresql(t *testing.T) {
	suite.Run(t, new(PostgresqlTestSuite))
}
