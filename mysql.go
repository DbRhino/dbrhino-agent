package main

import (
	"database/sql"
	"fmt"
	"strings"

	"github.com/flosch/pongo2"
	"github.com/go-sql-driver/mysql"
)

type Mysql struct {
	DB       *sql.DB
	Database *Database
}

func NewMysql(db *Database) *Mysql {
	return &Mysql{Database: db}
}

func (my *Mysql) connect(conn *Connection) error {
	conf := &mysql.Config{
		User:              conn.Database.Username,
		Passwd:            conn.Database.DecryptedPassword,
		Net:               "tcp",
		Addr:              fmt.Sprintf("%s:%d", conn.Database.Host, conn.Database.Port),
		InterpolateParams: true,
	}
	connStr := conf.FormatDSN()
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

const MYSQL_USER_HOST = "%" // FIXME make this configurable

func (my *Mysql) userExists(user *User) (bool, error) {
	sql := "SELECT user, host FROM mysql.user WHERE user = ? AND host = ?"
	rows, err := my.DB.Query(sql, user.Username, MYSQL_USER_HOST)
	if err != nil {
		return false, err
	}
	defer rows.Close()
	return rows.Next(), nil
}

func (my *Mysql) fullUsername(username string) string {
	quoted_uname := mysqlQuoteIdent(username)
	quoted_host := mysqlQuoteIdent(MYSQL_USER_HOST)
	return quoted_uname + "@" + quoted_host
}

func (my *Mysql) dropUser(user *User) error {
	sql := fmt.Sprintf("DROP USER %s", my.fullUsername(user.Username))
	_, err := my.DB.Exec(sql)
	return err
}

func (my *Mysql) updatePassword(user *User) error {
	sql := fmt.Sprintf("SET PASSWORD FOR %s = ?",
		my.fullUsername(user.Username))
	_, err := my.DB.Exec(sql, user.DecryptedPassword)
	return err
}

func mysqlQuoteIdent(ident string) string {
	return "`" + strings.Replace(ident, "`", "``", -1) + "`"
}

func (my *Mysql) createUser(user *User) error {
	sql := fmt.Sprintf("CREATE USER %s IDENTIFIED BY ?",
		my.fullUsername(user.Username))
	_, err := my.DB.Exec(sql, user.DecryptedPassword)
	return err
}

func (my *Mysql) cacheGlobalContextData() error {
	return nil
}

func (my *Mysql) createTemplateContext(username string) *pongo2.Context {
	return &pongo2.Context{
		"type":     "mysql",
		"username": my.fullUsername(username),
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
	sql := fmt.Sprintf("REVOKE ALL PRIVILEGES, GRANT OPTION FROM %s",
		my.fullUsername(username))
	_, err := my.DB.Exec(sql)
	return err
}
