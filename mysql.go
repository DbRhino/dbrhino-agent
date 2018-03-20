package main

import (
	"database/sql"
	"fmt"
	"strings"

	"github.com/flosch/pongo2"
	_ "github.com/go-sql-driver/mysql"
)

type Mysql struct {
	DB       *sql.DB
	Database *Database
}

func NewMysql(db *Database) *Mysql {
	return &Mysql{Database: db}
}

func (my *Mysql) connect(conn *Connection) error {
	connStr := fmt.Sprintf("%s:%s@tcp(%s:%d)/",
		conn.Database.Username, conn.Database.DecryptedPassword,
		conn.Database.Host, conn.Database.Port)
	DB, err := sql.Open("mysql", connStr)
	if err != nil {
		return err
	}
	my.DB = DB
	return nil
}

func (my *Mysql) getDB() *sql.DB {
	return my.DB
}

func (my *Mysql) getName() string {
	return my.Database.Name
}

const MYSQL_USER_HOST = "%" // FIXME

func (my *Mysql) userExists(user *User) (bool, error) {
	sql := "SELECT user, host FROM mysql.user WHERE user = ? AND host = ?"
	rows, err := my.DB.Query(sql, user.Username, MYSQL_USER_HOST)
	if err != nil {
		return false, err
	}
	defer rows.Close()
	return rows.Next(), nil
}

func (my *Mysql) dropUser(user *User) error {
	quoted_uname := mysqlQuoteIdent(user.Username)
	sql := fmt.Sprintf("DROP USER %s@`%s`", quoted_uname, MYSQL_USER_HOST)
	_, err := my.DB.Exec(sql)
	return err
}

func (my *Mysql) updatePassword(user *User) error {
	quoted_uname := mysqlQuoteIdent(user.Username)
	sql := fmt.Sprintf("SET PASSWORD FOR %s@`%s` = '%s'", quoted_uname,
		MYSQL_USER_HOST, user.DecryptedPassword)
	_, err := my.DB.Exec(sql)
	return err
}

func mysqlQuoteIdent(ident string) string {
	return "`" + strings.Replace(ident, "`", "``", -1) + "`"
}

func (my *Mysql) createUser(user *User) error {
	quoted_uname := mysqlQuoteIdent(user.Username)
	sql := fmt.Sprintf("CREATE USER %s@`%s` IDENTIFIED BY '%s'", quoted_uname,
		MYSQL_USER_HOST, user.DecryptedPassword)
	_, err := my.DB.Exec(sql)
	return err
}

func (my *Mysql) cacheGlobalContextData() error {
	return nil
}

func (my *Mysql) createTemplateContext(username string) *pongo2.Context {
	return &pongo2.Context{
		"type":     "mysql",
		"username": username,
	}
}

func (my *Mysql) filterGrants(orig []Grant, conn *Connection) []*Grant {
	var grants []*Grant
	for _, grant := range orig {
		if grant.DatabaseId == conn.Database.Id {
			grants = append(grants, &grant)
		}
	}
	return grants
}

func (my *Mysql) revokeEverything(username string) error {
	quoted_uname := mysqlQuoteIdent(username)
	sql := fmt.Sprintf("REVOKE ALL PRIVILEGES, GRANT OPTION FROM %s@`%s`",
		quoted_uname, MYSQL_USER_HOST)
	_, err := my.DB.Exec(sql)
	return err
}
