#!/bin/bash
# Push announce_mqtt.py failover fix to USB-reachable cams (NOPASSWD tee).
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)
SRC="${1:-/tmp/announce_mqtt.py}"
test -f "$SRC" || { echo "missing $SRC"; exit 1; }

for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  echo "======== $ip ========"
  if ! scp "${KEY[@]}" "$SRC" "admin@$ip:/tmp/announce_mqtt.py"; then
    echo "SCP_FAIL"; continue
  fi
  ssh "${KEY[@]}" "admin@$ip" bash -s <<'REMOTE' || echo SSH_FAIL
set -euo pipefail
sudo tee /usr/local/bin/bhvr-cam-announce >/dev/null </tmp/announce_mqtt.py
grep -q _mqtt_publish_failover /usr/local/bin/bhvr-cam-announce
grep -q _drop_stale_usb_routes /usr/local/bin/bhvr-cam-announce
python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -3
hostname
REMOTE
done
echo DONE
