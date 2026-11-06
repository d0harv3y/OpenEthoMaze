#!/bin/bash
# cam0 link=wifi while still plugged — why is usb_ok false?
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)

echo "=== roster ==="
bash /tmp/_snap_roster.sh 2>/dev/null || true

echo "=== NVR usb / neigh ==="
ip -br a | grep -E 'br-bhvr|usb' || true
ip neigh show dev br-bhvr 2>/dev/null | head -20 || true
ping -c 2 -W 1 192.168.7.41 2>&1 | tail -5

echo "=== mosquitto on USB path ==="
ss -lntp | grep 1883 || true
# can we connect to ourselves on br-bhvr?
python3 -c '
import socket
for h in ("192.168.7.1","127.0.0.1","10.248.238.22"):
    s=socket.socket(); s.settimeout(1.0)
    try:
        s.connect((h,1883)); print(h, "OK")
    except Exception as e:
        print(h, type(e).__name__, e)
    finally:
        s.close()
'

for ip in 192.168.7.41 10.248.238.167; do
  echo "======== ssh $ip ========"
  ssh "${KEY[@]}" "admin@$ip" bash -s <<'REMOTE' || { echo SSH_FAIL; continue; }
set +e
hostname
date -u +%H:%M:%SZ
ip -br a
echo "carrier=$(cat /sys/class/net/usb0/carrier 2>/dev/null || echo none)"
echo "oper=$(cat /sys/class/net/usb0/operstate 2>/dev/null || echo none)"
ip route | head -25
echo "--- broker ---"
cat /var/lib/bhvr/broker.env 2>/dev/null
echo "--- link_state ---"
cat /var/lib/bhvr/link_state.json 2>/dev/null; echo
cat ~/.cache/bhvr/link_state.json 2>/dev/null; echo
echo "--- tcp probes ---"
python3 - <<'PY'
import socket, subprocess
from pathlib import Path

def tcp(h, src=None, t=0.8):
    s=socket.socket(); s.settimeout(t)
    try:
        if src: s.bind((src,0))
        s.connect((h,1883)); return "OK"
    except OSError as e:
        return f"{type(e).__name__}:{e}"
    finally:
        s.close()

usb=None
for line in subprocess.check_output(["ip","-4","-o","a","show","dev","usb0"],text=True).splitlines():
    p=line.split()
    if len(p)>=4 and "/" in p[3]:
        usb=p[3].split("/")[0]
wifi=None
for line in subprocess.check_output(["ip","-4","-o","a","show","dev","wlan0"],text=True).splitlines():
    p=line.split()
    if len(p)>=4 and "/" in p[3]:
        wifi=p[3].split("/")[0]
print("usb_ip", usb, "wifi_ip", wifi)
print("carrier", Path("/sys/class/net/usb0/carrier").read_text().strip() if Path("/sys/class/net/usb0/carrier").is_file() else None)
print("tcp 192.168.7.1 no-bind", tcp("192.168.7.1"))
print("tcp 192.168.7.1 src=usb", tcp("192.168.7.1", usb))
print("tcp 10.248.238.22 no-bind", tcp("10.248.238.22"))
print("tcp 10.248.238.22 src=wifi", tcp("10.248.238.22", wifi))
for h in ("192.168.7.1","10.248.238.22"):
    print("route get", h, ":", subprocess.check_output(["ip","route","get",h],text=True).strip())
PY
echo "--- announce once ---"
python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -15
echo "--- announce markers ---"
grep -c _usb_link_usable /usr/local/bin/bhvr-cam-announce || true
grep -c _drop_stale_usb_routes /usr/local/bin/bhvr-cam-announce || true
REMOTE
done
