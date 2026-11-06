#!/bin/bash
# Thin wrapper — prefer /usr/local/bin/bhvr-cam-announce (Python, no apt deps).
exec /usr/local/bin/bhvr-cam-announce "$@"
