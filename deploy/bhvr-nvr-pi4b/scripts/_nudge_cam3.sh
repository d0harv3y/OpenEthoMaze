#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
IP=192.168.7.28
ssh "${KEY[@]}" "admin@$IP" 'pkill -9 rpicam-vid 2>/dev/null; pkill -9 nc 2>/dev/null; hostname; timeout 4 rpicam-vid -n -t 2500 --width 640 --height 480 --framerate 15 --codec h264 --inline --buffer-count 6 -o /tmp/health.h264; wc -c /tmp/health.h264' || echo "cam3 nudge FAIL"
