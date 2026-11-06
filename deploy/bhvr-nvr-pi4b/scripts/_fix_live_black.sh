#!/bin/bash
# Deploy UI + main settle fix; stop all idle previews; restart uvicorn once.
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
cp /tmp/bhvr-htu/index.html app/templates/index.html
cp /tmp/bhvr-htu/main.py app/main.py
# Stop any half-dead publishers
curl -sS -X POST http://127.0.0.1:8080/api/preview/stop || true
pkill -9 -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 2
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >"$HOME/bhvr-kiosk/uvicorn.log" 2>&1 &
sleep 3
# Sequential whep start (matches staggered UI)
for c in bhvr-cam0 bhvr-cam1 bhvr-cam2 bhvr-cam3; do
  echo "=== $c ==="
  curl -sS -m 120 -X POST "http://127.0.0.1:8080/api/preview/${c}/whep/start" || true
  echo
  sleep 1
done
curl -sS http://127.0.0.1:8080/api/health | python3 -c 'import sys,json; h=json.load(sys.stdin); print("transport", h.get("preview_transport"), "idle", h.get("preview_idle"))'
echo FIX_LIVE_DONE
