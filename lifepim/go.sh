#!/bin/bash
########################################################
# go.sh
# script to start the lifepim web interface
#


python ./web_app/welifepim.py &

xdg-open http://127.0.0.1:5000/ &
