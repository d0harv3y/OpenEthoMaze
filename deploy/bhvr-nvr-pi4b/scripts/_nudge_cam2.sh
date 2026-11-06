#!/bin/bash
# Soft-nudge flaky cam2 USB/SSH before ×4 litmus.
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
IP=192.168.7.31
echo "gadgets=$(lsusb | grep -c 1d6b:0104 || true)"
ssh "${KEY[@]}" "admin@$IP" 'pkill -9 rpicam-vid 2>/dev/null; pkill -9 nc 2>/dev/null; pkill -9 ffmpeg 2>/dev/null; hostname; uptime; free -h | head -2' || {
  echo "SSH dead — try usb reset path"
  exit 1
}
# brief encode smoke
ssh "${KEY[@]}" "admin@$IP" 'timeout 3 rpicam-vid -n -t 2000 --width 640 --height 480 --framerate 15 --codec h264 --inline -o /tmp/nudge.h264 && wc -c /tmp/nudge.h264' || echo "encode smoke FAIL"
echo "cam2 nudge done"
