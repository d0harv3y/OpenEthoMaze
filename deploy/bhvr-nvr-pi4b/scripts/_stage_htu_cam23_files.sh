#!/bin/bash
set -euo pipefail
sed -i 's/\r$//' /tmp/_push_htu_cam23.sh /tmp/bhvr-cam-htu-sample.service /tmp/bhvr-cam-htu-sample.timer 2>/dev/null || true
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)
for f in /tmp/htu21d.py /tmp/bhvr-cam-htu-sample.service /tmp/bhvr-cam-htu-sample.timer /tmp/_push_htu_cam23.sh; do
  test -f "$f" || { echo "missing $f"; exit 1; }
  ls -la "$f"
done
for ip in 192.168.7.31 192.168.7.28; do
  echo "SCP $ip"
  scp "${KEY[@]}" /tmp/htu21d.py /tmp/bhvr-cam-htu-sample.service /tmp/bhvr-cam-htu-sample.timer "admin@$ip:/tmp/"
done
echo "FILES_STAGED — run: bash /tmp/_push_htu_cam23.sh"
