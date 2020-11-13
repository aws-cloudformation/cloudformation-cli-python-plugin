#!/usr/bin/env bash
DIR=$(mktemp -d)
cd "$DIR"
ls -la
cfn init -t AWS::Foo::Bar $1 --use-docker
ls -la
mypy src/aws_foo_bar/ --strict --implicit-reexport
