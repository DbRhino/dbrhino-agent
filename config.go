package main

import (
	"io/ioutil"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v2"
)

const DATA_DIR = "~/.dbrhino"

type Config struct {
	AccessToken string `yaml:"access_token"`
	ServerUrl   string `yaml:"server_url"`
	Debug       bool   `yaml:"debug"`
}

func NewConfig() *Config {
	return &Config{
		Debug:     false,
		ServerUrl: "https://app.dbrhino.com",
	}
}

func makeDataDirectory() error {
	return os.Mkdir(expandUser(DATA_DIR), os.ModePerm)
}

func readConfig() (*Config, error) {
	conf := NewConfig()
	if !fileExists(conf.path()) {
		return conf, nil
	}
	yamlFile, err := ioutil.ReadFile(conf.path())
	if err != nil {
		return nil, err
	}
	err = yaml.Unmarshal(yamlFile, conf)
	if err != nil {
		return nil, err
	}
	return conf, nil
}

func (conf *Config) write() error {
	data, err := yaml.Marshal(conf)
	if err != nil {
		return err
	}
	err = ioutil.WriteFile(conf.path(), data, 0644)
	if err != nil {
		return err
	}
	return nil
}

func (conf *Config) path() string {
	return filepath.Join(expandUser(DATA_DIR), "config.yml")
}

func (conf *Config) privateKeyPath() string {
	return filepath.Join(expandUser(DATA_DIR), "agent.pem")
}

func (conf *Config) publicKeyPath() string {
	return filepath.Join(expandUser(DATA_DIR), "agent.pub")
}

func (conf *Config) pidFile() string {
	return filepath.Join(expandUser(DATA_DIR), "agent.pid")
}

func (conf *Config) logPath() string {
	return filepath.Join(expandUser(DATA_DIR), "agent.log")
}
