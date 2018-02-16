package main

import (
	"bufio"
	"crypto/rsa"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/op/go-logging"
)

var logger = logging.MustGetLogger("grants")

const AGENT_VERSION = "0.4.0-beta"

var fileFormat = logging.MustStringFormatter(
	`%{time:15:04:05.000} > %{level:.4s} %{message} <in %{shortfunc}>`,
)

var stderrFormat = logging.MustStringFormatter(
	`%{color}%{time:15:04:05.000} ▶ %{level:.4s}%{color:reset} %{message} <in %{shortfunc}>`,
)

func askUserForAccessToken() (string, error) {
	reader := bufio.NewReader(os.Stdin)
	fmt.Print("Please enter your access token: ")
	access_token, err := reader.ReadString('\n')
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(access_token), nil
}

func configureLogging(conf *Config) {
	f, err := os.OpenFile(conf.LogPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0640)
	if err != nil {
		logger.Error("Could not open file for logging: %s", err)
		return
	}
	fileBackend := logging.NewLogBackend(f, "", 0)
	fileFormatter := logging.NewBackendFormatter(fileBackend, fileFormat)
	if conf.Debug {
		stderrBackend := logging.NewLogBackend(os.Stderr, "", 0)
		stderrFormatter := logging.NewBackendFormatter(stderrBackend, stderrFormat)
		logging.SetBackend(fileFormatter, stderrFormatter)
	} else {
		logging.SetBackend(fileFormatter)
	}
}

func readAndHandleConfig() (*Config, error) {
	conf, err := readConfig()
	if err != nil {
		return nil, err
	}
	for conf.AccessToken == "" {
		logger.Infof("No access token found, but I'll wait")
		sleepDuration := time.Duration(10) * time.Second
		time.Sleep(sleepDuration)
		conf.readAccessToken()
	}
	return conf, nil
}

type Application struct {
	conf *Config
	key  *rsa.PrivateKey
}

func (app *Application) runGrantFetchAndApply() error {
	grantsResponse, err := fetchGrants(app.conf)
	if err != nil {
		return err
	}
	checkin := handleGrantsResponse(app, grantsResponse)
	_, err = sendCheckin(app, checkin)
	return err
}

func main() {
	makeConfigDir()
	conf, err := readAndHandleConfig()
	if err != nil {
		logger.Fatal(err)
	}
	configureLogging(conf)
	key, err := readOrGeneratePrivateKey(conf)
	if err != nil {
		logger.Fatal(err)
	}
	app := Application{
		conf: conf,
		key:  key,
	}
	_, err = sendPubkey(&app)
	if err != nil {
		logger.Fatal(err)
	}
	sleepDuration := time.Duration(30) * time.Second
	for {
		err = app.runGrantFetchAndApply()
		if err != nil {
			logger.Errorf("Unknown error during grant cycle: %s", err)
		}
		time.Sleep(sleepDuration)
	}
}
