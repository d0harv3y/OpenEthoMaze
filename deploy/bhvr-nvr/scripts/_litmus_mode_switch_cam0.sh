#!/bin/bash
# cam0 unplug→WiFi→SSH→WHEP litmus (grill rollout Q10).
# Usage on NVR:
#   bash _litmus_mode_switch_cam0.sh           # check current path
#   UNPLUG=1 bash _litmus_mode_switch_cam0.sh # wait for wifi announce after you unplug
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=30 -o StrictHostKeyChecking=accept-new)
CAM_ID="${CAM_ID:-bhvr-cam0}"

roster_json() { curl -sS -m 8 http://127.0.0.1:8080/api/cams; }

print_cam() {
  roster_json | python3 -c '
import json,sys,os
want=os.environ.get("CAM_ID","bhvr-cam0")
for c in json.load(sys.stdin).get("cameras") or []:
    if c.get("id")==want:
        print("id", c.get("id"))
        print("online", c.get("online"), "age_s", c.get("age_s"))
        print("ip", c.get("ip"), "link", c.get("link"))
        print("ips", c.get("ips"))
        break
else:
    print("MISSING", want)
    sys.exit(2)
'
}

echo "=== roster $CAM_ID ==="
CAM_ID="$CAM_ID" print_cam

ip=$(CAM_ID="$CAM_ID" roster_json | python3 -c '
import json,sys,os
want=os.environ.get("CAM_ID","bhvr-cam0")
for c in json.load(sys.stdin).get("cameras") or []:
    if c.get("id")==want:
        print(c.get("ip") or ""); break
')
link=$(CAM_ID="$CAM_ID" roster_json | python3 -c '
import json,sys,os
want=os.environ.get("CAM_ID","bhvr-cam0")
for c in json.load(sys.stdin).get("cameras") or []:
    if c.get("id")==want:
        print(c.get("link") or ""); break
')

if [[ "${UNPLUG:-}" == "1" ]]; then
  echo "Unplug $CAM_ID USB now. Waiting up to 90s for link=wifi ..."
  for _ in $(seq 1 18); do
    sleep 5
    link=$(CAM_ID="$CAM_ID" roster_json | python3 -c '
import json,sys,os
want=os.environ.get("CAM_ID","bhvr-cam0")
for c in json.load(sys.stdin).get("cameras") or []:
    if c.get("id")==want:
        print(c.get("link") or ""); break
')
    ip=$(CAM_ID="$CAM_ID" roster_json | python3 -c '
import json,sys,os
want=os.environ.get("CAM_ID","bhvr-cam0")
for c in json.load(sys.stdin).get("cameras") or []:
    if c.get("id")==want:
        print(c.get("ip") or ""); break
')
    echo "  link=$link ip=$ip"
    if [[ "$link" == "wifi" && "$ip" == 10.* ]]; then
      break
    fi
  done
fi

echo "=== SSH litmus $ip ==="
ssh "${KEY[@]}" "admin@$ip" 'hostname; ip -4 -br a; cat /var/lib/bhvr/broker.env 2>/dev/null || true'
echo "SSH_OK"

echo "=== WHEP start ==="
code=$(curl -sS -m 180 -o /tmp/whep_mode.json -w "%{http_code}" \
  -X POST "http://127.0.0.1:8080/api/preview/${CAM_ID}/whep/start")
echo "http=$code $(head -c 240 /tmp/whep_mode.json)"
[[ "$code" == "200" ]] || exit 1
echo "LITMUS_MODE_SWITCH_OK link=$link ip=$ip"
