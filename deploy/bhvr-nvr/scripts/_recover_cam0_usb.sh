#!/bin/bash
# Recover cam0 USB tether when iface is up but L3 to 192.168.7.1 is dead.
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new)
WIFI=10.248.238.167

echo "=== NVR before ==="
ip -br a | grep -E 'br-bhvr|usb' || true
bridge link 2>/dev/null | head -20 || true
# which usb* has the cam0 MAC?
ip neigh show 192.168.7.41 2>/dev/null || true

echo "=== bounce cam0 gadget over WiFi ==="
ssh "${KEY[@]}" "admin@$WIFI" bash -s <<'REMOTE'
set -euo pipefail
hostname
ip -br a
echo "--- restart gadget+dhcp ---"
sudo systemctl restart bhvr-cam-usb-gadget.service
sleep 2
sudo systemctl restart bhvr-cam-usb0-dhcp.service || sudo networkctl reconfigure usb0 || true
sleep 4
ip -br a
echo "carrier=$(cat /sys/class/net/usb0/carrier 2>/dev/null)"
# litmus MQTT via usb bind
python3 - <<'PY'
import socket, time
from pathlib import Path

def tcp(h, src, t=1.5):
    s=socket.socket(); s.settimeout(t)
    try:
        s.bind((src,0)); s.connect((h,1883)); return True
    except OSError as e:
        print("fail", e); return False
    finally:
        s.close()

usb=None
import subprocess
for line in subprocess.check_output(["ip","-4","-o","a","show","dev","usb0"],text=True).splitlines():
    p=line.split()
    if len(p)>=4 and "/" in p[3]:
        usb=p[3].split("/")[0]
print("usb", usb, "carrier", Path("/sys/class/net/usb0/carrier").read_text().strip())
print("mqtt_usb", tcp("192.168.7.1", usb) if usb else False)
PY
# force announce (may still be wifi until usb_ok)
python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -5
REMOTE

echo "=== NVR after ==="
sleep 2
ip -br a | grep -E 'br-bhvr|usb' || true
ip neigh show 192.168.7.41 2>/dev/null || true
ping -c 3 -W 2 192.168.7.41 2>&1 | tail -6

echo "=== wait for USB announce (15s) ==="
for i in 1 2 3 4 5; do
  sleep 3
  curl -sS -m 5 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("id")=="bhvr-cam0":
        print(c.get("link"), c.get("ip"), c.get("age_s"), c.get("ips"))
'
done
