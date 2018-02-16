package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io/ioutil"
	"net/http"
	"strings"
	"time"
)

func dbrhinoGetUrl(conf *Config, path string) string {
	return strings.TrimRight(conf.ServerUrl, "/") + path
}

func setHeaders(req *http.Request, conf *Config) {
	req.Header.Set("User-Agent", "dbrhino-agent")
	req.Header.Set("Accept-Language", "en-us")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+conf.AccessToken)
}

func doRequest(client *http.Client, req *http.Request, result interface{}) error {
	res, err := client.Do(req)
	if err != nil {
		return err
	}
	body, err := ioutil.ReadAll(res.Body)
	if err != nil {
		return err
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return errors.New(fmt.Sprintf("HTTP %d: %s", res.StatusCode, body))
	}
	// fmt.Print(string(body))
	return json.Unmarshal(body, result)
}

func dbrhinoGetRequest(conf *Config, path string, result interface{}) error {
	url := dbrhinoGetUrl(conf, path)
	client := http.Client{
		Timeout: time.Second * 10,
	}
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	setHeaders(req, conf)
	return doRequest(&client, req, result)
}

func dbrhinoPostRequest(conf *Config, path string, payload []byte,
	result interface{}) error {
	url := dbrhinoGetUrl(conf, path)
	client := http.Client{
		Timeout: time.Second * 10,
	}
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewBuffer(payload))
	if err != nil {
		return err
	}
	setHeaders(req, conf)
	return doRequest(&client, req, result)
}

func fetchGrants(conf *Config) (*GrantsResponse, error) {
	result := &GrantsResponse{}
	err := dbrhinoGetRequest(conf, "/api/grants", result)
	if err != nil {
		return nil, err
	}
	return result, nil
}

type SendPubkeyRequest struct {
	Pubkey []byte `json:"pubkey"`
}

func sendPubkey(app *Application) (*SendPubkeyResponse, error) {
	encoded, err := encodePublicKey(app.key, app.conf)
	if err != nil {
		return nil, err
	}
	payload, err := json.Marshal(SendPubkeyRequest{
		Pubkey: encoded,
	})
	if err != nil {
		return nil, err
	}
	result := &SendPubkeyResponse{}
	err = dbrhinoPostRequest(app.conf, "/api/agents/startup", payload, result)
	if err != nil {
		return nil, err
	}
	return result, nil
}

func sendCheckin(app *Application, checkin *CheckinRequest) (*SendCheckinResponse, error) {
	payload, err := json.Marshal(checkin)
	if err != nil {
		return nil, err
	}
	result := &SendCheckinResponse{}
	err = dbrhinoPostRequest(app.conf, "/api/agents/checkin", payload, result)
	if err != nil {
		return nil, err
	}
	return result, nil
}
