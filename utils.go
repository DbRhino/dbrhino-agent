package main

import (
	"os"
	"os/user"
	"path/filepath"
)

func fileExists(path string) bool {
	_, err := os.Stat(path)
	if err == nil {
		return true
	}
	if os.IsNotExist(err) {
		return false
	}
	panic(err)
}

func expandUser(path string) string {
	if path[:2] != "~/" {
		return path
	}
	usr, err := user.Current()
	if err != nil {
		panic(err)
	}
	dir := usr.HomeDir
	return filepath.Join(dir, path[2:])
}
