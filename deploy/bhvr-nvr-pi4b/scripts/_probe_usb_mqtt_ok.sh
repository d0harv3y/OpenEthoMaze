#!/bin/bash
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
for ip in 192.168.7.41 192.168.7.31 192.168.7.27 192.168.7.28; do
  echo "======== $ip ========"
  ssh "${KEY[@]}" "admin@$ip" bash -s <<'REMOTE'
hostname
echo "--- gw ---"
ip -4 route show dev usb0
echo "--- tcp 192.168.7.1:1883 from usb ---"
python3 - <<'PY'
import socket
usb="192.168.7.41"
# detect local usb ip
import subprocess
out=subprocess.check_output(["ip","-4","-o","addr","show","dev","usb0"], text=True)
# 2: usb0    inet 192.168.7.x/24
ip=None
for part in out.split():
    if "/" in part and part[0].isdigit():
        ip=part.split("/")[0]
        break
print("usb_ip", ip)
s=socket.socket(); s.settimeout(1.0)
try:
    if ip: s.bind((ip,0))
    s.connect(("192.168.7.1",1883)); print("TCP_OK", s.getsockname())
except Exception as e:
    print("TCP_FAIL", e)
finally:
    s.close()
# also to wifi NVR IP
s=socket.socket(); s.settimeout(1.0)
try:
    if ip: s.bind((ip,0))
    s.connect(("10.248.238.22",1883)); print("TCP_WIFI_IP_VIA_USB", "ok")
except Exception as e:
    print("TCP_WIFI_IP_VIA_USB", e)
finally:
    s.close()
PY
echo "--- link_state ---"
cat /var/lib/bhvr/link_state.json 2>/dev/null || cat ~/.cache/bhvr/link_state.json 2>/dev/null || echo none
echo "--- announce verbose ---"
python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -8 || true
REMOTE
done
echo "=== roster ==="
curl -sS -m 5 http://127.0.0.1:8080/api/cams | python3 -c '
import sys,json
d=json.load(sys.stdin)
for c in d.get("cameras") or []:
  print(c.get("id"), c.get("online"), c.get("link"), c.get("ip"))
'
echo PROBE_DONE
