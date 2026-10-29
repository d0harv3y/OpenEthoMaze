#!/bin/bash
set -euo pipefail
cp -f /tmp/bhvr-ks/kiosk_settings.py "$HOME/bhvr-kiosk/app/kiosk_settings.py"
pkill -f 'uvicorn app.main:app' || true
sleep 1
cd "$HOME/bhvr-kiosk"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 25); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.4
done
curl -sS -m 45 http://127.0.0.1:8080/api/kiosk/status | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
print("soft", d.get("soft_present"), "/", d.get("soft_total"))
print("tree", d.get("cam_tree"))
print("eligible", [c["id"] for c in d.get("eligible", []) if c.get("eligible")])
g = d.get("git") or {}
print("git", g.get("describe"), g.get("error"))
'
echo SMOKE_OK
