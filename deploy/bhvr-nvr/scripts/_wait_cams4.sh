#!/bin/bash
set -uo pipefail
for i in $(seq 1 20); do
  echo "try $i"
  out=$(bash "$HOME/deploy/bhvr-nvr/scripts/_diag_cam_ssh.sh")
  echo "$out"
  ups=$(echo "$out" | grep -c '^UP' || true)
  if [[ "$ups" -ge 4 ]]; then
    echo ALL4
    exit 0
  fi
  sleep 5
done
echo NOT_ALL4
exit 1
