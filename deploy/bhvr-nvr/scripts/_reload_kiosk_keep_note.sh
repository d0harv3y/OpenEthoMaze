#!/bin/bash
# Restart kiosk uvicorn so main.py link field loads. Idle WHEP publishers drop.
set +e
cd "$HOME/bhvr-kiosk"
pkill -f 'uvicorn app.main:app' || true
sleep 2
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>uvicorn.log 2>&1 &
sleep 3
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 - <<'PY'
import sys, json
d = json.load(sys.stdin)
for c in d.get("cameras", []):
    print(c.get("id"), c.get("link"), c.get("ip"), "online="+str(c.get("online")))
PY
grep -q 'announce_link_mode' app/main.py && echo main_has_link_helper=yes
grep -q 'ONLINE · USB' app/templates/index.html && echo template_has_usb_badge=yes
