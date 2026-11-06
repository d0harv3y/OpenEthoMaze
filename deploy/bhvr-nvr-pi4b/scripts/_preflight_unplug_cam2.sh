#!/bin/bash
# Preflight before USB→WiFi unplug timing on cam2. Run on NVR while still plugged.
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)
IP_USB=192.168.7.31

echo "=== roster cam2 ==="
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("id")=="bhvr-cam2":
        print({k:c.get(k) for k in ("id","ip","link","online","age_s","ips","temp_c")})
'

echo "=== cam2 (USB SSH) ==="
ssh "${KEY[@]}" "admin@$IP_USB" bash -s <<'REMOTE'
hostname
ip -br a
echo "--- broker.env ---"
cat /var/lib/bhvr/broker.env 2>/dev/null || echo MISSING_broker.env
echo "--- announce markers ---"
grep -c MQTT_BROKER_WIFI /usr/local/bin/bhvr-cam-announce || true
grep -c _usb_link_usable /usr/local/bin/bhvr-cam-announce || true
echo "--- usb usable litmus ---"
python3 - <<'PY'
import socket
from pathlib import Path
def carrier():
    p=Path("/sys/class/net/usb0/carrier")
    return p.is_file() and p.read_text().strip()=="1"
def tcp(host,port=1883,t=0.8):
    try:
        socket.create_connection((host,port),timeout=t).close(); return True
    except OSError: return False
print("usb0_carrier", carrier())
print("mqtt_192.168.7.1", tcp("192.168.7.1"))
wifi=None
try:
    import subprocess
    out=subprocess.check_output(["ip","-4","-o","addr","show","dev","wlan0"],text=True)
    for line in out.splitlines():
        parts=line.split()
        if len(parts)>=4 and "/" in parts[3]:
            wifi=parts[3].split("/")[0]
except Exception as e:
    print("wlan0", e)
print("wifi_ip", wifi)
PY
REMOTE

echo
echo "Ready if: ONLINE·USB, ips has usb+wifi, broker.env has MQTT_BROKER_WIFI,"
echo "and wlan0 has an address. Then: unplug USB data, watch roster age/link."
echo "Expect ONLINE·WiFi within ~10–20s (one announce tick)."
