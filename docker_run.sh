#!/bin/sh

docker run --tty --interactive --rm --name="jobmanager-client" jobmanager-client:latest $*

