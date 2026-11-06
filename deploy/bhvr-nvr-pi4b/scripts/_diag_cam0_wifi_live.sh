#!/bin/bash
set +e
echo "=== roster ==="
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("id")=="bhvr-cam0":
        print({k:c.get(k) for k in ("online","age_s","ip","link","ips","ts")})
'
echo "=== health idle ==="
curl -sS -m 5 http://127.0.0.1:8080/api/health | python3 -c 'import json,sys; print(json.load(sys.stdin).get("preview_idle"))'

KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new)
WIFI=$(curl -sS -m 5 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("id")=="bhvr-cam0":
        print((c.get("ips") or {}).get("wifi") or c.get("ip") or "")
')
echo "wifi=$WIFI"
echo "=== ssh litmus ==="
ssh "${KEY[@]}" "admin@$WIFI" 'hostname; uptime; ip -4 -br a; cat /var/lib/bhvr/broker.env; grep -c _usb_link_usable /usr/local/bin/bhvr-cam-announce; journalctl -u bhvr-cam-announce.service -n 6 --no-pager' 2>&1 | head -40

echo "=== ping rtt ==="
ping -c 4 -W 2 "$WIFI" | tail -5

echo "=== whep start ==="
code=$(curl -sS -m 180 -o /tmp/whep_cam0.json -w "%{http_code}" -X POST \
  http://127.0.0.1:8080/api/preview/bhvr-cam0/whep/start)
echo "http=$code $(head -c 280 /tmp/whep_cam0.json)"
echo "=== logs ==="
tail -25 /tmp/bhvr-preview-bhvr-cam0-cam.log 2>/dev/null
tail -15 /tmp/bhvr-preview-bhvr-cam0-remux.log 2>/dev/null
