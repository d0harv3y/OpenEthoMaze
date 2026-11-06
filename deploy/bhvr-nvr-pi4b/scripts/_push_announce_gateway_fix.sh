#!/bin/bash
# Push announce_mqtt.py gateway fix to all USB cams; force one-shot announce.
set -euo pipefail
SRC="${1:-/tmp/announce_mqtt.py}"
test -f "$SRC"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  echo "======== $ip ========"
  if ! ping -c 1 -W 1 "$ip" >/dev/null 2>&1; then
    echo PING_FAIL; continue
  fi
  scp "${KEY[@]}" "$SRC" "admin@$ip:/tmp/announce_mqtt.py"
  ssh "${KEY[@]}" "admin@$ip" bash -s <<'REMOTE'
set -euo pipefail
sudo tee /usr/local/bin/bhvr-cam-announce >/dev/null </tmp/announce_mqtt.py
grep -q '_looks_like_ipv4' /usr/local/bin/bhvr-cam-announce
# clear sticky wifi-only broker cache so USB gw can win
sudo tee /var/lib/bhvr/broker.env >/dev/null <<'EOF' || true
MQTT_BROKER=192.168.7.1
MQTT_PORT=1883
MQTT_BROKER_WIFI=10.248.238.22
EOF
# best-effort user-writable cache too
mkdir -p "$HOME/.cache/bhvr" 2>/dev/null || true
rm -f "$HOME/.cache/bhvr/link_state.json" /var/lib/bhvr/link_state.json 2>/dev/null || true
timeout -k 2 15 python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -3
sudo systemctl restart bhvr-cam-announce.timer 2>/dev/null || true
hostname
REMOTE
done
echo "=== roster (after 8s) ==="
sleep 8
curl -sS -m 5 http://127.0.0.1:8080/api/cams | python3 -c '
import sys,json
d=json.load(sys.stdin)
for c in sorted(d.get("cameras") or [], key=lambda x: x.get("id") or ""):
  ips=c.get("ips") or {}
  print(c.get("id"), "online="+str(c.get("online")), "link="+str(c.get("link")),
        "ip="+str(c.get("ip")), "usb="+str(ips.get("usb")), "wifi="+str(ips.get("wifi")))
'
echo ANNOUNCE_GW_FIX_DONE
