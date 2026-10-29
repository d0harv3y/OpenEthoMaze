#!/bin/bash
# cam0 stuck on WiFi with no 192.168.7.x — bounce gadget+DHCP over WiFi SSH.
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new)
WIFI=10.248.238.167

echo "=== NVR usb ifaces before ==="
ip -br a | grep -E 'usb|br-bhvr' || true
ip neigh show dev br-bhvr || true

ssh "${KEY[@]}" "admin@$WIFI" bash -s <<'REMOTE'
set -euo pipefail
hostname
ip -br a
echo "--- bounce gadget ---"
sudo systemctl restart bhvr-cam-usb-gadget.service
sleep 2
sudo systemctl restart bhvr-cam-usb0-dhcp.service || sudo networkctl reconfigure usb0 || true
sleep 3
ip -br a
echo "carrier=$(cat /sys/class/net/usb0/carrier 2>/dev/null || echo none)"
python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -5
REMOTE

echo "=== NVR after ==="
sleep 2
ip -br a | grep -E 'usb|br-bhvr' || true
ip neigh show dev br-bhvr || true
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("id")=="bhvr-cam0":
        print(c.get("id"), c.get("link"), c.get("ip"), c.get("ips"), "age", c.get("age_s"))
'
