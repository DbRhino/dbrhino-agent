package main

import (
	"github.com/stretchr/testify/assert"
	"testing"
)

func TestSomething(t *testing.T) {
	conf := &Config{}
	app := &Application{conf, nil}
	grantsResponse := &GrantsResponse{
		Connections: []Connection{
			Connection{
				Id: 1,
				Database: &Database{
					Id:                1,
					Name:              "foo",
					Type:              "postgresql",
					Host:              "localhost",
					Port:              5432,
					Username:          "buck",
					DecryptedPassword: "password",
					DefaultDatabase:   "dbrhino_agent_tests",
				},
				DbName:    "dbrhino_agent_tests",
				IsDefault: true,
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
				Statements: []string{
					"grant connect on database {{database}} to {{username}}",
				},
				Version:  "abc",
				Username: "testUser123",
			},
		},
	}
	checkin := handleGrantsResponse(app, grantsResponse)
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
}
