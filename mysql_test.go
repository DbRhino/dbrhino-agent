package main

import (
	"database/sql"
	"log"
	"testing"

	"github.com/go-sql-driver/mysql"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/suite"
)

type MysqlTestSuite struct {
	suite.Suite
	App *Application
}

const MY_MASTER_USER = "root"
const MY_MASTER_PASS = "password"
const MY_TESTER_USER = "testUser123"
const MY_TESTER_PASS = "PasW';drop table `foo`"

func myTesterUri(username string, password string) string {
	conf := &mysql.Config{
		User:   username,
		Passwd: password,
		Net:    "tcp",
		Addr:   "localhost:3306",
	}
	return conf.FormatDSN()
}

func withMysqlTestConnection(uri string, f func(*sql.DB)) {
	DB, err := sql.Open("mysql", uri)
	if err != nil {
		log.Fatalf("Error opening test database %s", err)
	}
	defer DB.Close()
	f(DB)
}

func mysqlTestGrantResponse(statements []string) *GrantsResponse {
	return &GrantsResponse{
		Connections: []Connection{
			Connection{
				Id: 1,
				Database: &Database{
					Id:                1,
					Name:              "mysql_test",
					Type:              "mysql",
					Host:              "localhost",
					Port:              3306,
					Username:          MY_MASTER_USER,
					DecryptedPassword: MY_MASTER_PASS,
					DefaultDatabase:   "dbrhino_agent_tests",
				},
				DbName: "dbrhino_agent_tests",
			},
		},
		Users: []User{
			User{
				Id:                1,
				DecryptedPassword: MY_TESTER_PASS,
				Active:            true,
				Username:          MY_TESTER_USER,
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
				Username:     MY_TESTER_USER,
			},
		},
	}
}

func (suite *MysqlTestSuite) SetupTest() {
	conf := &Config{}
	app := &Application{conf, nil}
	suite.App = app
	withMysqlTestConnection(myTesterUri(MY_MASTER_USER, MY_MASTER_PASS), func(DB *sql.DB) {
		DB.Exec("drop user " + MY_TESTER_USER)
		tx, err := DB.Begin()
		assert.Nil(suite.T(), err)
		execShouldPass(suite.T(), DB, "drop schema if exists test_schema")
		execShouldPass(suite.T(), DB, "create schema test_schema")
		execShouldPass(suite.T(), DB, "create table test_schema.abc (x integer, y text)")
		execShouldPass(suite.T(), DB, "insert into test_schema.abc values (1, 'a'), (2, 'b')")
		execShouldPass(suite.T(), DB, "create table test_schema.def (x integer)")
		execShouldPass(suite.T(), DB, "insert into test_schema.def values (1), (2)")
		assert.Nil(suite.T(), tx.Commit())
	})
}

func (suite *MysqlTestSuite) TestBasicGrant() {
	grantsResponse := mysqlTestGrantResponse([]string{
		"GRANT SELECT ON test_schema.* TO {{username}}",
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
	withMysqlTestConnection(myTesterUri(MY_TESTER_USER, MY_TESTER_PASS), func(DB *sql.DB) {
		execShouldPass(t, DB, "select * from test_schema.abc")
	})
}

func TestMysql(t *testing.T) {
	suite.Run(t, new(MysqlTestSuite))
}
