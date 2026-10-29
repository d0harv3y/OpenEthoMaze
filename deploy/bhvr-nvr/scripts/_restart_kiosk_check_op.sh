#!/bin/bash
set -euxo pipefail
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
cd "$HOME/bhvr-kiosk"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 25); do
  curl -sS -m 2 http://127.0.0.1:8080/api/operator/settings >/tmp/op.json 2>/dev/null && break
  sleep 0.4
done
.venv/bin/python -c 'import json; d=json.load(open("/tmp/op.json")); print(d["science_ask"]); print(d["settings"]["profile"], d["settings"]["soft_fps"])'
