#!/bin/bash
set -euxo pipefail
SRC=/tmp/bhvr-fps-res
KIOSK=$HOME/bhvr-kiosk
cp -f "$SRC/main.py" "$KIOSK/app/main.py"
cp -f "$SRC/index.html" "$KIOSK/app/templates/index.html"
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
cd "$KIOSK"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >/tmp/kiosk-uvicorn.log 2>&1 &
sleep 2
curl -sS http://127.0.0.1:8080/api/health
echo
grep -n 'withResolution\|PREVIEW_WIDTH\|preview_width' "$KIOSK/app/templates/index.html" | head -10
echo DEPLOY_FPS_RES_OK
