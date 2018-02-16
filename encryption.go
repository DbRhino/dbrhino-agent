package main

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/asn1"
	"encoding/base64"
	"encoding/pem"
	"errors"
	"io/ioutil"
	"os"
)

func privateKeyFileExists(conf *Config) bool {
	return fileExists(conf.PrivateKeyPath)
}

func encodePublicKey(key *rsa.PrivateKey, conf *Config) ([]byte, error) {
	pub := key.PublicKey
	asn1Bytes, err := asn1.Marshal(pub)
	if err != nil {
		return nil, err
	}
	var pemBlock = &pem.Block{
		Type:  "PUBLIC KEY",
		Bytes: asn1Bytes,
	}
	return pem.EncodeToMemory(pemBlock), nil
}

func generateAndWritePrivateKey(conf *Config) (*rsa.PrivateKey, error) {
	logger.Info("Generating an RSA private key")
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return nil, err
	}
	pemBlock := pem.Block{
		Type:  "RSA PRIVATE KEY",
		Bytes: x509.MarshalPKCS1PrivateKey(key),
	}
	certOut, err := os.Create(conf.PrivateKeyPath)
	if err != nil {
		return nil, err
	}
	defer certOut.Close()
	certOut.Chmod(0600)
	err = pem.Encode(certOut, &pemBlock)
	if err != nil {
		return nil, err
	}
	return key, nil
}

func readPrivateKey(conf *Config) (*rsa.PrivateKey, error) {
	data, err := ioutil.ReadFile(conf.PrivateKeyPath)
	if err != nil {
		return nil, err
	}
	pemBlock, _ := pem.Decode(data)
	if pemBlock == nil {
		return nil, errors.New("No PEM block could be decoded")
	}
	key, err := x509.ParsePKCS1PrivateKey(pemBlock.Bytes)
	if err != nil {
		return nil, err
	}
	return key, nil
}

func readOrGeneratePrivateKey(conf *Config) (*rsa.PrivateKey, error) {
	if privateKeyFileExists(conf) {
		return readPrivateKey(conf)
	}
	return generateAndWritePrivateKey(conf)
}

func decryptPassword(app *Application, b64password string) (string, error) {
	data, err := base64.StdEncoding.DecodeString(b64password)
	if err != nil {
		return "", err
	}
	decrypted, err := app.key.Decrypt(rand.Reader, data, nil)
	if err != nil {
		return "", err
	}
	return string(decrypted[:len(decrypted)-sha256.Size]), nil
}
