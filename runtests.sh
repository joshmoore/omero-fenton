#!/bin/sh

export PYTHONPATH=./SleekXMPP:./twitter
exec python -munittest "$@" test-mmmbot

