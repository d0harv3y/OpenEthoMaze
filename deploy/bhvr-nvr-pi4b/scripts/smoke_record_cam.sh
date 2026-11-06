#!/bin/bash
set -euo pipefail
KEY="${HOME}/.ssh/id_ed25519_bhvr"
CAM="${1:-admin@10.248.235.74}"
ssh -i "$KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$CAM" \
  "sudo mkdir -p /run/bhvr /data/bhvr/current && \
   echo PROFILE=480p30 | sudo tee /run/bhvr/record.env >/dev/null && \
   echo OUT=/data/bhvr/current/video.mp4 | sudo tee -a /run/bhvr/record.env >/dev/null && \
   echo PTS=/data/bhvr/current/timestamps.pts | sudo tee -a /run/bhvr/record.env >/dev/null && \
   echo DURATION=3000 | sudo tee -a /run/bhvr/record.env >/dev/null && \
   sudo systemctl restart bhvr-cam-record.service && \
   sleep 6 && \
   systemctl is-active bhvr-cam-record.service || true && \
   sudo systemctl stop bhvr-cam-record.service || true && \
   ls -la /data/bhvr/current/"
