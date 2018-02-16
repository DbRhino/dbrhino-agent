package main

import (
	"errors"
	"fmt"
)

type Database struct {
	Id                int    `json:"id"`
	Name              string `json:"name"`
	Type              string `json:"dbtype"`
	Host              string `json:"host"`
	Port              int    `json:"port"`
	Username          string `json:"master_username"`
	EncryptedPassword string `json:"master_password"`
	DecryptedPassword string `json:"-"`
	DefaultDatabase   string `json:"default_database"`
}

type Connection struct {
	Id        int       `json:"id"`
	Database  *Database `json:"database"`
	DbName    string    `json:"name"`
	IsDefault bool      `json:"is_default"`
}

type User struct {
	Id                int    `json:"id"`
	EncryptedPassword string `json:"password"`
	DecryptedPassword string `json:"-"`
	Active            bool   `json:"active"`
	Username          string `json:"username"`
	DatabaseId        int    `json:"database_id"`
}

type Grant struct {
	Id           int      `json:"id"`
	DatabaseId   int      `json:"database_id"`
	ConnectionId int      `json:"connection_id"`
	UserId       int      `json:"database_user_id"`
	Statements   []string `json:"statements"`
	Version      string   `json:"version"`
	Username     string   `json:"username"`
}

type GrantsResponse struct {
	Connections []Connection `json:"connections"`
	Users       []User       `json:"database_users"`
	Grants      []Grant      `json:"grants"`
}

func (gr *GrantsResponse) defaultConnection(databaseId int) (*Connection, error) {
	for _, conn := range gr.Connections {
		if conn.Database.Id == databaseId && conn.IsDefault {
			return &conn, nil
		}
	}
	return nil, errors.New(fmt.Sprintf("Default conn not found for DB %d", databaseId))
}

func (gr *GrantsResponse) usersForDatabase(info *Database) []User {
	var users []User
	for _, user := range gr.Users {
		if user.DatabaseId == info.Id {
			users = append(users, user)
		}
	}
	return users
}

type Result string

const (
	RESULT_APPLIED          Result = "applied"
	RESULT_UNKNOWN_ERROR           = "unknown_error"
	RESULT_REVOKED                 = "revoked"
	RESULT_NO_PASSWORD             = "no_user_password"
	RESULT_CONNECTION_ISSUE        = "connection_issue"
)

type UserResult struct {
	UserId int    `json:"database_user_id"`
	Result Result `json:"result"`
	Error  error  `json:"error"`
}

func newUserResult(user *User, result Result) *UserResult {
	return &UserResult{UserId: user.Id, Result: result}
}

func unknownErrorUserResult(user *User, err error) *UserResult {
	res := newUserResult(user, RESULT_UNKNOWN_ERROR)
	res.Error = err
	return res
}

func (ur *UserResult) log() {
	if ur.Error != nil {
		logger.Errorf("Error updating user %d: %s", ur.UserId, ur.Error)
	} else {
		logger.Debugf("User apply result for user %d: %s", ur.UserId, ur.Result)
	}
}

type GrantResult struct {
	GrantId int    `json:"grant_id"`
	Version string `json:"version"`
	Result  Result `json:"result"`
	Error   error  `json:"error"`
}

func newGrantResult(grant *Grant, result Result) *GrantResult {
	return &GrantResult{
		GrantId: grant.Id,
		Version: grant.Version,
		Result:  result,
	}
}

func unknownErrorGrantResult(grant *Grant, err error) *GrantResult {
	res := newGrantResult(grant, RESULT_UNKNOWN_ERROR)
	res.Error = err
	return res
}

type CheckinRequest struct {
	AgentVersion string         `json:"agent_version"`
	UserResults  []*UserResult  `json:"user_results"`
	GrantResults []*GrantResult `json:"grant_results"`
}

func newCheckinResult() *CheckinRequest {
	return &CheckinRequest{
		AgentVersion: AGENT_VERSION,
		UserResults:  []*UserResult{},
		GrantResults: []*GrantResult{},
	}
}

type SendPubkeyResponse struct {
	PubkeyUpdated bool `json:"pubkey_updated"`
}

type SendCheckinResponse struct{}
