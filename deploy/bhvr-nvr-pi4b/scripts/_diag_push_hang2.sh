#!/bin/bash
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
ssh "${KEY[@]}" admin@192.168.7.28 bash -s <<'REMOTE'
set +e
for pid in $(pgrep -f 'bash -s'); do
  echo "=== pid $pid ==="
  tr '\0' ' ' </proc/$pid/cmdline; echo
  ls -l /proc/$pid/fd 2>/dev/null | head -20
  echo "-- children --"
  ps --ppid $pid -o pid,cmd 2>/dev/null || true
done
echo '=== sudo ==='
ps aux | grep -E 'sudo|tee|systemctl|daemon-reload' | grep -v grep
echo '=== last announce bin head ==='
head -c 80 /usr/local/bin/bhvr-cam-announce | od -c | head -2
REMOTE
