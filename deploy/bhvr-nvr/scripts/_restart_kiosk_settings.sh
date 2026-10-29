#!/bin/bash
set -euo pipefail
cp -f /tmp/bhvr-ks/kiosk_settings.py "$HOME/bhvr-kiosk/app/kiosk_settings.py"
pkill -f 'uvicorn app.main:app' || true
sleep 1
cd "$HOME/bhvr-kiosk"
.venv/bin/python -c 'from app import kiosk_settings; print("import_ok", len(kiosk_settings.SOFT_INSTALL))'
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 30); do
  if curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1; then
    echo health_ok
    break
  fi
  sleep 0.4
done
curl -sS -m 5 http://127.0.0.1:8080/api/health | head -c 200; echo
bash /tmp/_smoke_usb_push.sh bhvr-cam3
