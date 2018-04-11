package main

import (
	"bufio"
	"crypto/rsa"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/op/go-logging"
	"github.com/sevlyar/go-daemon"
	"github.com/urfave/cli"
)

var logger = logging.MustGetLogger("grants")

const AGENT_VERSION = "0.5.1"

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

func configureLogging() {
	f, err := os.OpenFile(getLogPath(), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0640)
	if err != nil {
		logger.Error("Could not open file for logging: %s", err)
		return
	}
	fileBackend := logging.NewLogBackend(f, "", 0)
	fileFormatter := logging.NewBackendFormatter(fileBackend, fileFormat)
	fileLeveled := logging.AddModuleLevel(fileFormatter)
	fileLeveled.SetLevel(logging.INFO, "")
	if debugModeEnabled() {
		stderrBackend := logging.NewLogBackend(os.Stderr, "", 0)
		stderrFormatter := logging.NewBackendFormatter(stderrBackend, stderrFormat)
		logging.SetBackend(fileLeveled, stderrFormatter)
	} else {
		logging.SetBackend(fileLeveled)
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

func initializationError(err error) {
	sleepDuration := time.Duration(5) * time.Second
	logger.Errorf("Initialization error: %s", err)
	time.Sleep(sleepDuration)
}

func applicationInitialization() *Application {
	configureLogging()
	var conf *Config
	var err error
	var key *rsa.PrivateKey
	for {
		conf, err = readAndHandleConfig()
		if err == nil {
			break
		}
		initializationError(err)
	}
	for {
		key, err = readOrGeneratePrivateKey(conf)
		if err == nil {
			break
		}
		initializationError(err)
	}
	app := &Application{
		conf: conf,
		key:  key,
	}
	for {
		_, err = sendPubkey(app)
		if err == nil {
			break
		}
		initializationError(err)
	}
	return app
}

func runServer(c *cli.Context) error {
	app := applicationInitialization()
	sleepDuration := time.Duration(30) * time.Second
	for {
		err := app.runGrantFetchAndApply()
		if err != nil {
			logger.Errorf("Unknown error during grant cycle: %s", err)
		}
		time.Sleep(sleepDuration)
	}
	return nil
}

func runOnce(c *cli.Context) error {
	app := applicationInitialization()
	err := app.runGrantFetchAndApply()
	if err != nil {
		logger.Errorf("Unknown error during grant cycle: %s", err)
	}
	return err
}

func runDaemon(c *cli.Context) error {
	cntxt := &daemon.Context{
		PidFileName: "pid",
		LogFileName: "log",
		PidFilePerm: 0644,
		LogFilePerm: 0640,
	}
	d, err := cntxt.Reborn()
	if err != nil {
		logger.Fatal("Unable to run: ", err)
	}
	if d != nil {
		return nil
	}
	defer cntxt.Release()
	return runServer(c)
}

func main() {
	app := cli.NewApp()
	app.Name = "dbrhino-agent"
	app.Version = AGENT_VERSION
	app.Copyright = "(c) 2018 The Buck Codes Here, LLC"
	app.HelpName = "dbrhino-agent"
	app.Usage = "Agent application for https://www.dbrhino.com"
	app.Commands = []cli.Command{
		cli.Command{
			Name:   "server",
			Action: runServer,
		},
		cli.Command{
			Name:   "once",
			Action: runOnce,
		},
		cli.Command{
			Name:   "daemon",
			Action: runDaemon,
		},
	}
	app.Run(os.Args)
}
