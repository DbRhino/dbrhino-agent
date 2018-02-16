package main

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
)

const (
	DEFAULT_CONFIG_DIR = "/etc/dbrhino-agent"
	DEFAULT_LOG_PATH   = "/var/log/dbrhino-agent.log"
	DEFAUT_SERVER_URL  = "https://app.dbrhino.com"

	ENV_CONFIG_DIR = "DBRHINO_AGENT_CONFIG_DIR"
	ENV_DEBUG      = "DBRHINO_AGENT_DEBUG"
	ENV_SERVER_URL = "DBRHINO_AGENT_SERVER_URL"
	ENV_LOG_PATH   = "DBRHINO_AGENT_LOG_PATH"
)

func debugModeEnabled() bool {
	return os.Getenv(ENV_DEBUG) != ""
}

func getLogPath() string {
	path := os.Getenv(ENV_LOG_PATH)
	if path == "" {
		path = DEFAULT_LOG_PATH
	}
	return path
}

func getConfigDir() string {
	dir := os.Getenv(ENV_CONFIG_DIR)
	if dir == "" {
		dir = DEFAULT_CONFIG_DIR
	}
	return dir
}

type Config struct {
	AccessToken    string
	ServerUrl      string
	PrivateKeyPath string
	PublicKeyPath  string
}

func readConfig() (*Config, error) {
	conf := &Config{}
	conf.readServerUrl()
	conf.readAccessToken()
	conf.readPrivateKeyPath()
	conf.readPublicKeyPath()
	return conf, nil
}

func (c *Config) readServerUrl() {
	if env := os.Getenv(ENV_SERVER_URL); env != "" {
		c.ServerUrl = env
	} else {
		c.ServerUrl = DEFAUT_SERVER_URL
	}
}

func (c *Config) readAccessToken() {
	path := filepath.Join(getConfigDir(), "token")
	dat, err := ioutil.ReadFile(path)
	if err != nil {
		logger.Errorf("could not read access token file: %s", err)
	} else {
		c.AccessToken = strings.TrimSpace(string(dat))
	}
}

func (c *Config) readPrivateKeyPath() {
	c.PrivateKeyPath = filepath.Join(getConfigDir(), "agent.pem")
}

func (c *Config) readPublicKeyPath() {
	c.PublicKeyPath = filepath.Join(getConfigDir(), "agent.pub")
}
