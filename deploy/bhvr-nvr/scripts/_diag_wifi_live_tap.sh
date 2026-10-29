#!/bin/bash
# Why ONLINE·WiFi tap → "no LIVE": try whep/start + SSH litmus for wifi cams.
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)

echo "=== roster ==="
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    print(c.get("id"), "link="+str(c.get("link")), "online="+str(c.get("online")),
          "age="+str(c.get("age_s")), "ip="+str(c.get("ip")), "ips="+str(c.get("ips")))
'

echo "=== preview_idle ==="
curl -sS -m 5 http://127.0.0.1:8080/api/health | python3 -c '
import json,sys
h=json.load(sys.stdin)
print("transport", h.get("preview_transport"))
print("preview_idle", h.get("preview_idle"))
'

# Pick first online wifi cam
CAM=$(curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("online") and c.get("link")=="wifi" and c.get("ip"):
        print(c["id"]); print(c["ip"], file=sys.stderr); break
')
IP=$(curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("online") and c.get("link")=="wifi" and c.get("ip"):
        print(c["ip"]); break
')
echo "target cam=$CAM ip=$IP"
[[ -n "$CAM" && -n "$IP" ]] || { echo "no online wifi cam"; exit 0; }

echo "=== SSH litmus $IP ==="
ssh "${KEY[@]}" -o ConnectTimeout=30 "admin@$IP" 'hostname; ip -br a | head -5' 2>&1 | head -20

echo "=== POST whep/start ==="
curl -sS -m 90 -X POST "http://127.0.0.1:8080/api/preview/${CAM}/whep/start" -w "\nHTTP %{http_code}\n" 2>&1 | tail -40

echo "=== cam/remux logs (tail) ==="
tail -30 "/tmp/bhvr-preview-${CAM}-cam.log" 2>/dev/null || echo no_cam_log
echo "---"
tail -30 "/tmp/bhvr-preview-${CAM}-remux.log" 2>/dev/null || echo no_remux_log

echo "=== kiosk log tail ==="
tail -40 /tmp/kiosk-web.log 2>/dev/null || true
