#!/bin/bash
# Probe: after USB unplug, which cams announce WLAN IPs and accept SSH?
set -eu
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no)

echo "=== kiosk preview knobs ==="
grep -E '^(  )?(nvr_host|whep_ingest|transport|udp_port):' "$HOME/bhvr-kiosk/config.yaml" || true

echo "=== NVR IPv4 ==="
ip -4 -br addr | grep -v '^lo'

echo "=== roster ==="
curl -sS http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
j=json.load(sys.stdin)
for c in j.get("cameras") or []:
    ip=c.get("ip","?")
    kind="USB?" if str(ip).startswith("192.168.7.") else ("WLAN" if str(ip).startswith("10.") else "?")
    print("%s online=%s age=%ss ip=%s (%s)" % (
        c.get("id"), c.get("online"), c.get("age_s"), ip, kind))
'

echo "=== SSH each roster IP ==="
curl -sS http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
j=json.load(sys.stdin)
for c in j.get("cameras") or []:
    print(c.get("ip",""))
' | while read -r ip; do
  [[ -z "$ip" ]] && continue
  echo -n "ssh $ip: "
  if out=$(ssh "${KEY[@]}" "admin@$ip" 'hostname; ip -4 -br a show wlan0 2>/dev/null; ip route | head -2' 2>&1); then
    echo OK
    echo "$out" | sed 's/^/  /'
  else
    echo FAIL
    echo "$out" | sed 's/^/  /' | head -4
  fi
done
