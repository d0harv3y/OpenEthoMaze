#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)
ssh "${KEY[@]}" admin@10.248.238.167 bash -s <<'REMOTE'
hostname
ip -br a
echo "--- broker.env ---"
cat /var/lib/bhvr/broker.env 2>/dev/null || echo missing
echo "--- announce markers ---"
grep -c MQTT_BROKER_WIFI /usr/local/bin/bhvr-cam-announce || true
grep -c _usb_link_usable /usr/local/bin/bhvr-cam-announce || true
REMOTE
