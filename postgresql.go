package main

import (
	"database/sql"
	"errors"
	"fmt"

	"github.com/flosch/pongo2"
	pglib "github.com/lib/pq"
)

type PgCatalog struct {
	Database string
	Schemas  []string
}

type PgFlavor interface {
	createUserSql(*User) string
	updatePasswordSql(*User) string
}

type PostgreSQL struct {
	Flavor        PgFlavor
	DB            *sql.DB
	CachedCatalog *PgCatalog
	Database      *Database
}

func NewPostgreSQL(db *Database, flavor PgFlavor) *PostgreSQL {
	return &PostgreSQL{
		Flavor:   flavor,
		Database: db,
	}
}

func (pg *PostgreSQL) connect(conn *Connection) error {
	// TODO support sslmode and other options as needed
	// TODO what if the password has string characters? url encoding necessary?
	// or maybe just enclosing in single quotes?
	connStr := fmt.Sprintf("postgres://%s:%s@%s:%d/%s?sslmode=disable",
		conn.Database.Username, conn.Database.DecryptedPassword,
		conn.Database.Host, conn.Database.Port, conn.DbName)
	DB, err := sql.Open("postgres", connStr)
	if err != nil {
		return err
	}
	pg.DB = DB
	return nil
}

func (pg *PostgreSQL) getDB() *sql.DB {
	return pg.DB
}

func (pg *PostgreSQL) getName() string {
	return pg.Database.Name
}

func (pg *PostgreSQL) discoverCurrentDb() (string, error) {
	sql := "SELECT current_database()"
	rows, err := pg.DB.Query(sql)
	if err != nil {
		return "", err
	}
	defer rows.Close()
	if !rows.Next() {
		return "", errors.New("Current database query returned no results")
	}
	var db string
	if err = rows.Scan(&db); err != nil {
		return "", err
	}
	return db, nil
}

func (pg *PostgreSQL) discoverAllSchemas() ([]string, error) {
	sql := `SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT LIKE 'pg_%'
        AND schema_name != 'information_schema'`
	rows, err := pg.DB.Query(sql)
	var schemas []string
	if err != nil {
		return schemas, err
	}
	defer rows.Close()
	for rows.Next() {
		var schemaName string
		if err = rows.Scan(&schemaName); err != nil {
			return schemas, err
		}
		schemas = append(schemas, schemaName)
	}
	return schemas, nil
}

func (pg *PostgreSQL) cacheGlobalContextData() error {
	db, err := pg.discoverCurrentDb()
	if err != nil {
		return err
	}
	schemas, err := pg.discoverAllSchemas()
	if err != nil {
		return err
	}
	pg.CachedCatalog = &PgCatalog{
		Database: db,
		Schemas:  schemas,
	}
	return nil
}

func (pg *PostgreSQL) createTemplateContext(username string) *pongo2.Context {
	return &pongo2.Context{
		"database": pglib.QuoteIdentifier(pg.CachedCatalog.Database),
		"schemas":  MapString(pg.CachedCatalog.Schemas, pglib.QuoteIdentifier),
		"username": pglib.QuoteIdentifier(username),
	}
}

func (pg *PostgreSQL) userExists(user *User) (bool, error) {
	sql := "SELECT usename FROM pg_catalog.pg_user WHERE usename = $1"
	rows, err := pg.DB.Query(sql, user.Username)
	if err != nil {
		return false, err
	}
	defer rows.Close()
	return rows.Next(), nil
}

func (pg *PostgreSQL) updatePassword(user *User) error {
	if err := checkPasswordChars(user.DecryptedPassword); err != nil {
		return err
	}
	sql := pg.Flavor.updatePasswordSql(user)
	if _, err := pg.DB.Exec(sql); err != nil {
		return err
	}
	return nil
}

func (pg *PostgreSQL) dropUser(user *User) error {
	if err := pg.revokeEverything(user.Username); err != nil {
		return err
	}
	quoted_uname := pglib.QuoteIdentifier(user.Username)
	sql := fmt.Sprintf("DROP USER %s", quoted_uname)
	if _, err := pg.DB.Exec(sql); err != nil {
		return err
	}
	return nil
}

func (pg *PostgreSQL) createUser(user *User) error {
	sql := pg.Flavor.createUserSql(user)
	if _, err := pg.DB.Exec(sql); err != nil {
		return err
	}
	return nil
}

func (pg *PostgreSQL) filterGrants(orig []Grant, conn *Connection) []*Grant {
	var grants []*Grant
	for _, grant := range orig {
		if grant.ConnectionId == conn.Id {
			grants = append(grants, &grant)
		}
	}
	return grants
}

func (pg *PostgreSQL) revokeEverything(username string) error {
	quoted_uname := pglib.QuoteIdentifier(username)
	quoted_db := pglib.QuoteIdentifier(pg.CachedCatalog.Database)
	sql := fmt.Sprintf("REVOKE ALL ON DATABASE %s FROM %s", quoted_db, quoted_uname)
	if _, err := pg.DB.Exec(sql); err != nil {
		return err
	}
	schema_sqls := []string{
		"REVOKE ALL ON SCHEMA %s FROM %s",
		"REVOKE ALL ON ALL TABLES IN SCHEMA %s FROM %s",
		"REVOKE ALL ON ALL SEQUENCES IN SCHEMA %s FROM %s",
		"REVOKE ALL ON ALL FUNCTIONS IN SCHEMA %s FROM %s",
	}
	for _, sqlBase := range schema_sqls {
		for _, schema := range pg.CachedCatalog.Schemas {
			quoted_schema := pglib.QuoteIdentifier(schema)
			sql = fmt.Sprintf(sqlBase, quoted_schema, quoted_uname)
			if _, err := pg.DB.Exec(sql); err != nil {
				return err
			}
		}
	}
	return nil
}

type PgNative struct {
}

func (pg *PgNative) createUserSql(user *User) string {
	quoted_uname := pglib.QuoteIdentifier(user.Username)
	return fmt.Sprintf("CREATE USER %s PASSWORD '%s'", quoted_uname,
		// See the notes in updatePassword around security and why the password
		// is injected directly into this string
		user.DecryptedPassword)
}

func (pg *PgNative) updatePasswordSql(user *User) string {
	quoted_uname := pglib.QuoteIdentifier(user.Username)
	return fmt.Sprintf("ALTER USER %s WITH ENCRYPTED PASSWORD '%s'", quoted_uname,
		// The password is injected directly into the SQL statement rather than
		// using bindings because of https://github.com/lib/pq/issues/708. But
		// we have matched the password against the regex in order to confirm
		// there won't be any SQL injection issues.
		user.DecryptedPassword)
}

type Redshift struct {
}

func (rd *Redshift) createUserSql(user *User) string {
	quoted_uname := pglib.QuoteIdentifier(user.Username)
	return fmt.Sprintf("CREATE USER %s PASSWORD '%s'", quoted_uname,
		// See notes above about password being injected directly here.
		user.DecryptedPassword)
}

func (rd *Redshift) updatePasswordSql(user *User) string {
	quoted_uname := pglib.QuoteIdentifier(user.Username)
	return fmt.Sprintf("ALTER USER %s PASSWORD '%s'", quoted_uname,
		// See notes above about password being injected directly here.
		user.DecryptedPassword)
}
