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

// Example format string. Everything except the message has a custom color
// which is dependent on the log level. Many fields have a custom output
// formatting too, eg. the time returns the hour down to the milli second.
var format = logging.MustStringFormatter(
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

func configureLogging() {
	// For demo purposes, create two backend for os.Stderr.
	backend1 := logging.NewLogBackend(os.Stderr, "", 0)
	backend2 := logging.NewLogBackend(os.Stderr, "", 0)
	// For messages written to backend2 we want to add some additional
	// information to the output, including the used log level and the name of
	// the function.
	backend2Formatter := logging.NewBackendFormatter(backend2, format)
	// Only errors and more severe messages should be sent to backend1
	backend1Leveled := logging.AddModuleLevel(backend1)
	backend1Leveled.SetLevel(logging.ERROR, "")
	// Set the backends to be used.
	logging.SetBackend(backend1Leveled, backend2Formatter)
}

func readAndHandleConfig() (*Config, error) {
	conf, err := readConfig()
	if err != nil {
		return nil, err
	}
	if conf.AccessToken == "" {
		access_token, err := askUserForAccessToken()
		if err != nil {
			return nil, err
		}
		conf.AccessToken = access_token
		if err = conf.write(); err != nil {
			return nil, err
		}
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
	makeDataDirectory()
	configureLogging()
	conf, err := readAndHandleConfig()
	if err != nil {
		logger.Fatal(err)
	}
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
