#!/bin/bash
# After replug: snap roster, force announce on USB cams, show LIVE readiness.
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)

echo "=== usb net / neigh ==="
ip -br a | grep -E 'usb|br-bhvr' || true
ip neigh show dev br-bhvr 2>/dev/null | head -20 || true

echo "=== roster ==="
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    print(c.get("id"), "link="+str(c.get("link")), "online="+str(c.get("online")),
          "age="+str(c.get("age_s")), "ip="+str(c.get("ip")), "ips="+str(c.get("ips")),
          "temp="+str(c.get("temp_c")))
'

echo "=== nudge announce on 192.168.7.* ==="
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  echo "-------- $ip --------"
  ssh "${KEY[@]}" "admin@$ip" bash -s <<'REMOTE' 2>&1 | head -40 || echo SSH_FAIL
hostname
ip -br a
echo "carrier=$(cat /sys/class/net/usb0/carrier 2>/dev/null || echo none)"
cat /var/lib/bhvr/broker.env 2>/dev/null || echo no_broker
# force USB preference check + announce
python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -3
REMOTE
done

echo "=== roster after nudge ==="
sleep 2
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    print(c.get("id"), "link="+str(c.get("link")), "online="+str(c.get("online")),
          "age="+str(c.get("age_s")), "ip="+str(c.get("ip")), "ips="+str(c.get("ips")))
'
