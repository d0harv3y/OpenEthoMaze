#!/bin/bash
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
ssh "${KEY[@]}" admin@192.168.7.28 bash -s <<'REMOTE'
set +e
echo '=== procs ==='
ps aux | grep -E 'tee|systemctl|announce|bhvr-cam-soft' | grep -v grep
echo '=== soft dir ==='
ls -la /tmp/bhvr-cam-soft 2>&1 | head -25
echo '=== units ==='
systemctl is-active bhvr-cam-announce.timer 2>&1
systemctl is-active bhvr-cam-announce.service 2>&1
echo '=== bash -s children ==='
pgrep -af 'bash -s' || true
REMOTE
