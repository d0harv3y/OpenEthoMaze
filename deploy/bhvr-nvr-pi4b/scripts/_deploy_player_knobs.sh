#!/bin/bash
# Deploy mpegts player-knob litmus surface onto ~/bhvr-kiosk. Run ON NVR.
# Expects /tmp/bhvr-player-knobs/{main.py,index.html} already scp'd.
set -euxo pipefail
SRC=/tmp/bhvr-player-knobs
KIOSK="${HOME}/bhvr-kiosk"
cp -f "$SRC/main.py" "$KIOSK/app/main.py"
cp -f "$SRC/index.html" "$KIOSK/app/templates/index.html"

pkill -f 'uvicorn app.main:app' 2>/dev/null || true
pkill -f 'uvicorn app.main' 2>/dev/null || true
sleep 1
cd "$KIOSK"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 20); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.5
done
curl -sS -m 5 http://127.0.0.1:8080/api/health; echo
# smoke diag
curl -sS -m 5 -X DELETE http://127.0.0.1:8080/api/diag/live-player; echo
curl -sS -m 5 -X POST http://127.0.0.1:8080/api/diag/live-player \
  -H 'Content-Type: application/json' \
  -d '{"cam_id":"bhvr-cam0","chase":false,"stash":128,"paint_n":1,"buffered_s":0.4,"stream_fps":10.0}'
echo
curl -sS -m 5 'http://127.0.0.1:8080/api/diag/live-player?since_s=10'; echo
echo DEPLOY_OK
