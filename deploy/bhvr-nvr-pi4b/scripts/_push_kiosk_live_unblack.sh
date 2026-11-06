#!/bin/bash
set -euo pipefail
DEST="$HOME/bhvr-kiosk"
cp -f /tmp/kiosk_main.py "$DEST/app/main.py"
cp -f /tmp/kiosk_preview.py "$DEST/app/preview.py"
cp -f /tmp/kiosk_index.html "$DEST/app/templates/index.html"
cd "$DEST"
.venv/bin/python -c 'from app.main import _free_cam_encode_hosts; print("ok")'
# Stop all idle previews cleanly then restart web
curl -sS -m 5 -X POST http://127.0.0.1:8080/api/preview/stop >/dev/null 2>&1 || true
pkill -f 'uvicorn app.main:app' || true
sleep 1
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 25); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.3
done
# Warm one USB cam LIVE
CAM=$(curl -sS -m 5 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("online") and c.get("link")=="usb":
        print(c["id"]); break
')
echo "warm $CAM"
if [[ -n "$CAM" ]]; then
  curl -sS -m 60 -X POST "http://127.0.0.1:8080/api/preview/${CAM}/whep/start" -w "\nHTTP %{http_code}\n" | tail -5
fi
curl -sS -m 5 http://127.0.0.1:8080/api/health | python3 -c 'import json,sys; h=json.load(sys.stdin); print("idle", h.get("preview_idle"))'
echo DONE
