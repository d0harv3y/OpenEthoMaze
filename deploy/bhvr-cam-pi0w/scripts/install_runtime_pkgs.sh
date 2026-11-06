#!/bin/bash
# Online install of runtime packages for bhvr-cam (needs internet / hotspot).
# Air-gap: use offline/README.md + debs/ instead.
# Uses sudo -n (passwordless apt must be in /etc/sudoers.d — see firstboot).
set -euo pipefail

sudo -n apt-get update -qq
sudo -n apt-get install -y --no-install-recommends \
  rpicam-apps \
  ffmpeg \
  mosquitto-clients

echo "runtime packages:"
command -v rpicam-vid
command -v ffmpeg
ffmpeg -version 2>&1 | head -1
rpicam-vid --help 2>&1 | head -1 || true
