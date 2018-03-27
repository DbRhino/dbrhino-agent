# DbRhino Agent

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Installation](#installation)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

The agent application for [DbRhino](https://www.dbrhino.com) - the easiest way
to manage your database grants.

## Installation

```
go get github.com/dbrhino/dbrhino-agent
```

## Releasing

1. Update version in `main.go`
1. Commit and push
1. Run `./release`
1. In `dbrhino-agent-debian` repository:
    1. Update the VERSION file
    1. Add an entry to the changelog
    1. Run `./build.bash`
    1. Run `./upload.bash`
