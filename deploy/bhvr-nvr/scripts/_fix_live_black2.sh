#!/bin/bash
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
cp /tmp/bhvr-htu/index.html app/templates/index.html
cp /tmp/bhvr-htu/main.py app/main.py
cp /tmp/bhvr-htu/preview.py app/preview.py
curl -sS -X POST http://127.0.0.1:8080/api/preview/stop || true
# Kill stray ssh/ffmpeg preview leftovers
pkill -f 'bhvr-preview|rpicam-vid -n -t 0' 2>/dev/null || true
pkill -9 -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 2
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >"$HOME/bhvr-kiosk/uvicorn.log" 2>&1 &
sleep 3
for c in bhvr-cam0 bhvr-cam1 bhvr-cam2 bhvr-cam3; do
  echo "=== $c ==="
  curl -sS -m 180 -X POST "http://127.0.0.1:8080/api/preview/${c}/whep/start" || true
  echo
  sleep 2
done
curl -sS http://127.0.0.1:8080/api/health | python3 -c 'import sys,json; h=json.load(sys.stdin); print("idle", h.get("preview_idle"))'
echo FIX2_DONE
