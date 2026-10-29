#!/bin/bash
# Restart kiosk web so MQTT subscriber reconnects; verify roster ages drop.
set -euo pipefail
cd "$HOME/bhvr-kiosk"
echo "=== before ==="
curl -sS -m 5 http://127.0.0.1:8080/api/cams | .venv/bin/python -c '
import sys,json,time
d=json.load(sys.stdin)
for c in d.get("cameras") or []:
  print(c.get("id"), "online", c.get("online"), "age_s", round(float(c.get("age_s") or -1),1))
'
pkill -f 'uvicorn app.main:app' || true
sleep 1
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 40); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.3
done
echo "waiting for MQTT announces..."
sleep 12
echo "=== after ==="
curl -sS -m 5 http://127.0.0.1:8080/api/cams | .venv/bin/python -c '
import sys,json
d=json.load(sys.stdin)
ok=0
for c in d.get("cameras") or []:
  age=float(c.get("age_s") or 99999)
  on=bool(c.get("online"))
  print(c.get("id"), "online", on, "age_s", round(age,1))
  if on and age < 180:
    ok += 1
print("ONLINE_FRESH", ok)
'
echo FIX_MQTT_DONE
