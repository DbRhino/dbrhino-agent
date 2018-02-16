package main

import (
	"bytes"
	"database/sql"
	"errors"
	"fmt"
	"html/template"
	"regexp"
	"strings"
)

type DatabaseImpl interface {
	connect(*Connection) error
	getDB() *sql.DB
	getName() string
	userExists(*User) (bool, error)
	dropUser(*User) error
	updatePassword(*User) error
	createUser(*User) error
	cacheGlobalContextData() error
	createGrantContext(string) interface{}
	filterGrants([]Grant, *Connection) []*Grant
	revokeEverything(string) error
}

var PASSWORD_REGEX = regexp.MustCompile(`(?i)^[a-z0-9 ]+$`)

func checkPasswordChars(password string) error {
	matched := PASSWORD_REGEX.MatchString(password)
	if !matched {
		return errors.New("Passwords may only contain letters, numbers, and spaces")
	}
	return nil
}

func splitSqlBlock(sqlBlock string) []string {
	splitted := strings.Split(sqlBlock, ";")
	var results []string
	for _, sql := range splitted {
		trimmed := strings.TrimSpace(sql)
		if trimmed != "" {
			results = append(results, trimmed)
		}
	}
	return results
}

func updateUser(app *Application, grantsResponse *GrantsResponse,
	connRegistry *ConnRegistry, user *User) *UserResult {
	conn, err := grantsResponse.defaultConnection(user.DatabaseId)
	if err != nil {
		return unknownErrorUserResult(user, err)
	}
	regItem := (*connRegistry)[conn.Id]
	if regItem.Error != nil {
		return newUserResult(user, RESULT_CONNECTION_ISSUE)
	}
	if user.EncryptedPassword == "" {
		return newUserResult(user, RESULT_NO_PASSWORD)
	}
	userPw, err := decryptPassword(app, user.EncryptedPassword)
	if err != nil {
		return unknownErrorUserResult(user, err)
	}
	user.DecryptedPassword = userPw
	impl := &regItem.Impl
	exists, err := (*impl).userExists(user)
	if err != nil {
		return unknownErrorUserResult(user, err)
	}
	if !exists && !user.Active {
		return newUserResult(user, RESULT_APPLIED)
	}
	if !user.Active {
		if err := (*impl).dropUser(user); err != nil {
			return unknownErrorUserResult(user, err)
		}
		return newUserResult(user, RESULT_REVOKED)
	}
	if err := checkPasswordChars(user.DecryptedPassword); err != nil {
		return unknownErrorUserResult(user, err)
	}
	if exists {
		if err := (*impl).updatePassword(user); err != nil {
			return unknownErrorUserResult(user, err)
		}
		return newUserResult(user, RESULT_APPLIED)
	}
	if err := (*impl).createUser(user); err != nil {
		return unknownErrorUserResult(user, err)
	}
	return newUserResult(user, RESULT_APPLIED)
}

func applyGrantStatements(impl *DatabaseImpl, grant *Grant) *GrantResult {
	grantContext := (*impl).createGrantContext(grant.Username)
	for _, stmt := range grant.Statements {
		tmpl, err := template.New("sql").Parse(stmt)
		if err != nil {
			// FIXME return more specific error that the template could not be parsed
			return unknownErrorGrantResult(grant, err)
		}
		var tpl bytes.Buffer
		if err = tmpl.Execute(&tpl, grantContext); err != nil {
			return unknownErrorGrantResult(grant, err)
		}
		sqls := splitSqlBlock(tpl.String())
		for _, sql := range sqls {
			logger.Debugf("(%s) SQL: %s", (*impl).getName(), sql)
			if _, err := (*impl).getDB().Exec(sql); err != nil {
				return unknownErrorGrantResult(grant, err)
			}
		}
	}
	return newGrantResult(grant, RESULT_APPLIED)
}

func applyGrant(connRegistry *ConnRegistry, grant *Grant) *GrantResult {
	regItem := (*connRegistry)[grant.ConnectionId]
	if regItem.Error != nil {
		return newGrantResult(grant, RESULT_CONNECTION_ISSUE)
	}
	impl := &regItem.Impl
	txn, err := (*impl).getDB().Begin()
	var grantRes *GrantResult = nil
	if err != nil {
		return unknownErrorGrantResult(grant, err)
	}
	if err = (*impl).revokeEverything(grant.Username); err != nil {
		txn.Rollback()
		return unknownErrorGrantResult(grant, err)
	}
	logger.Debugf("(%s) Revoked everything for %s", (*impl).getName(), grant.Username)
	grantRes = applyGrantStatements(impl, grant)
	if err := grantRes.Error; err != nil {
		txn.Rollback()
	} else if err := txn.Commit(); err != nil {
		logger.Errorf("(%s) Error committing transaction: %s", (*impl).getName(), err)
		grantRes = unknownErrorGrantResult(grant, err)
	}
	return grantRes
}

type RegistryItem struct {
	Error error
	Impl  DatabaseImpl
}

func (ri *RegistryItem) setAndLogError(err error) {
	ri.Error = err
	logger.Errorf("registry item error: %s", err)
}

type ConnRegistry map[int]*RegistryItem

func handleGrantsResponse(app *Application, grantsResponse *GrantsResponse) *CheckinRequest {
	connRegistry := ConnRegistry{}
	for _, conn := range grantsResponse.Connections {
		regItem := &RegistryItem{}
		connRegistry[conn.Id] = regItem
		db := conn.Database
		switch db.Type {
		case "postgresql":
			regItem.Impl = NewPostgreSQL(db, PgFlavor(&PgNative{}))
		case "redshift":
			regItem.Impl = NewPostgreSQL(db, PgFlavor(&Redshift{}))
		case "mysql":
			regItem.Impl = NewMysql(db)
		default:
			regItem.setAndLogError(errors.New(fmt.Sprintf("Unknown database type: %s", db.Type)))
			continue
		}
		connPw, err := decryptPassword(app, db.EncryptedPassword)
		if err != nil {
			regItem.setAndLogError(err)
			continue
		}
		db.DecryptedPassword = connPw
		if err := regItem.Impl.connect(&conn); err != nil {
			regItem.setAndLogError(errors.New(fmt.Sprintf("Error connecting to database: %s", err)))
			continue
		}
		defer regItem.Impl.getDB().Close()
		if err := regItem.Impl.cacheGlobalContextData(); err != nil {
			regItem.setAndLogError(err)
			continue
		}
	}
	checkin := newCheckinResult()
	for _, user := range grantsResponse.Users {
		userResult := updateUser(app, grantsResponse, &connRegistry, &user)
		userResult.log()
		checkin.UserResults = append(checkin.UserResults, userResult)
	}
	for _, grant := range grantsResponse.Grants {
		grantResult := applyGrant(&connRegistry, &grant)
		checkin.GrantResults = append(checkin.GrantResults, grantResult)
	}
	return checkin
}
