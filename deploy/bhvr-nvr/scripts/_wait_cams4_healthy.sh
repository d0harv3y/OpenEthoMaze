#!/bin/bash
# Wait until all 4 cams SSH and can produce a short h264 file.
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
IPS=(192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28)
for attempt in $(seq 1 15); do
  echo "attempt $attempt"
  bash "$HOME/deploy/bhvr-nvr/scripts/_diag_cam_ssh.sh"
  ok=0
  for ip in "${IPS[@]}"; do
    if ssh "${KEY[@]}" "admin@$ip" \
      'pkill -9 rpicam-vid 2>/dev/null; pkill -9 nc 2>/dev/null; timeout 4 rpicam-vid -n -t 2500 --width 640 --height 480 --framerate 15 --codec h264 --inline --buffer-count 6 -o /tmp/health.h264 && test $(wc -c </tmp/health.h264) -gt 50000' \
      >/dev/null 2>&1; then
      echo "healthy $ip"
      ok=$((ok + 1))
    else
      echo "unhealthy $ip"
    fi
  done
  if [[ "$ok" -eq 4 ]]; then
    echo ALL4_HEALTHY
    exit 0
  fi
  sleep 6
done
echo NOT_HEALTHY
exit 1
