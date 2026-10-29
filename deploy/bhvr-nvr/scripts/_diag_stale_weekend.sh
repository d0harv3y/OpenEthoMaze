#!/bin/bash
# Weekend STALE triage: broker, roster, USB, Invite path.
set -euo pipefail
echo "=== clock ==="
date -u; uptime
echo "=== mosquitto ==="
systemctl is-active mosquitto 2>/dev/null || systemctl is-active mosquitto.service 2>/dev/null || true
pgrep -af mosquitto | head -5 || echo "no mosquitto proc"
ss -ltnp 2>/dev/null | grep -E ':1883|:1883' || netstat -ltn 2>/dev/null | grep 1883 || true
echo "=== kiosk web ==="
curl -sS -m 3 http://127.0.0.1:8080/api/health 2>&1 | head -c 300; echo
echo "=== roster (/api/cams) ==="
curl -sS -m 5 http://127.0.0.1:8080/api/cams 2>&1 | python3 -c '
import sys,json
try:
  d=json.load(sys.stdin)
except Exception as e:
  print("parse fail",e); sys.exit(0)
for c in d.get("cameras") or []:
  print(c.get("id"), "online="+str(c.get("online")), "link="+str(c.get("link")),
        "ip="+str(c.get("ip")), "age_s="+str(c.get("age_s")))
' 2>/dev/null || curl -sS -m 5 http://127.0.0.1:8080/api/cams | head -c 400; echo
echo "=== USB gadget host ==="
ip -br a | grep -E 'usb|enx|192.168.7' || true
lsusb 2>/dev/null | head -20 || true
echo "=== recent mqtt (if mosquitto_sub) ==="
if command -v mosquitto_sub >/dev/null; then
  timeout 3 mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/+/state' -v 2>&1 | head -20 || echo "(no messages in 3s)"
else
  echo "no mosquitto_sub"
fi
echo "=== cam USB IPs ping ==="
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=4 -o StrictHostKeyChecking=accept-new)
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  if ping -c 1 -W 1 "$ip" >/dev/null 2>&1; then
    echo -n "PING_OK $ip "
    ssh "${KEY[@]}" "admin@$ip" 'hostname; systemctl is-active bhvr-cam-announce.timer 2>/dev/null; systemctl is-active bhvr-cam-announce.service 2>/dev/null; ip -br a | grep -E "usb0|wlan0"' 2>&1 | tr '\n' ' '
    echo
  else
    echo "PING_FAIL $ip"
  fi
done
echo DIAG_STALE_DONE
