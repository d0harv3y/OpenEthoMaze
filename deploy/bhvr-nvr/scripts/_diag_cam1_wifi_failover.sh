#!/bin/bash
# cam1 USB→WiFi STALE dig (run on NVR).
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)

echo "=== roster ==="
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json, sys
for c in json.load(sys.stdin).get("cameras", []):
    if c.get("id") != "bhvr-cam1":
        continue
    keys = ("id","ip","link","online","age_s","temp_c","ips","ts")
    print({k: c.get(k) for k in keys})
'

echo "=== find cam1 (usb + wifi scan) ==="
# Last known from roster + common wifi range probe via mqtt retain topic
mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/bhvr-cam1/state' -C 1 -W 3 -v 2>/dev/null || true

# Try USB IP and any wifi IP from retained JSON
CAM_JSON=$(mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/bhvr-cam1/state' -C 1 -W 3 2>/dev/null || true)
echo "retain=$CAM_JSON"
IPS=$(python3 -c '
import json,sys,re
s=sys.stdin.read().strip()
if not s: sys.exit(0)
try: d=json.loads(s)
except Exception: sys.exit(0)
ips=[]
if d.get("ip"): ips.append(d["ip"])
for v in (d.get("ips") or {}).values():
    if v and v not in ips: ips.append(v)
print(" ".join(ips))
' <<<"$CAM_JSON")
echo "candidate_ips=$IPS"

# Also ping-sweep recent wifi from arp/neigh on wlan/br
echo "=== neigh 10.248 ==="
ip neigh | grep -E '10\.248\.' | head -30 || true

for ip in $IPS 192.168.7.27; do
  [[ -z "$ip" ]] && continue
  echo "======== ssh $ip ========"
  ssh "${KEY[@]}" "admin@$ip" bash -s <<'REMOTE' || { echo SSH_FAIL; continue; }
set +e
hostname
date -u +%Y-%m-%dT%H:%M:%SZ
ip -br a
echo "usb0_carrier=$(cat /sys/class/net/usb0/carrier 2>/dev/null || echo none)"
echo "usb0_oper=$(cat /sys/class/net/usb0/operstate 2>/dev/null || echo none)"
ip route | head -20
echo "NET_PREFER=${NET_PREFER:-}"
echo "MQTT_BROKER=${MQTT_BROKER:-}"
echo "MQTT_BROKER_WIFI=${MQTT_BROKER_WIFI:-}"
ls -la /var/lib/bhvr/ 2>/dev/null | head -20
cat /var/lib/bhvr/announce_link_state 2>/dev/null || true
cat /run/bhvr/announce_link_state 2>/dev/null || true
systemctl is-active bhvr-cam-announce.timer bhvr-cam-announce.service 2>&1
systemctl cat bhvr-cam-announce.timer 2>/dev/null | head -25
# TCP litmus to USB gw vs wifi broker
python3 - <<'PY'
import socket, os
for host,port,label in [
    ("192.168.7.1", 1883, "usb_mqtt"),
    (os.environ.get("MQTT_BROKER_WIFI") or "10.248.238.22", 1883, "wifi_mqtt"),
]:
    s=socket.socket(); s.settimeout(2.0)
    try:
        s.connect((host,port)); print(label, host, "OK")
    except Exception as e:
        print(label, host, "FAIL", type(e).__name__, e)
    finally:
        s.close()
PY
echo "--- announce ---"
python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -5
REMOTE
done
