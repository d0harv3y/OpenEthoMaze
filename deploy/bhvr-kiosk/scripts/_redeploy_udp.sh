#!/bin/bash
set -uo pipefail
cp /tmp/bhvr-kiosk-deploy/main.py /home/admin/bhvr-kiosk/app/main.py
cp /tmp/bhvr-kiosk-deploy/preview.py /home/admin/bhvr-kiosk/app/preview.py
cp /tmp/bhvr-kiosk-deploy/_smoke_preview_udp.sh /tmp/_smoke_preview_udp.sh
pkill -f 'uvicorn app.main' 2>/dev/null || true
sleep 1
cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2
curl -s http://127.0.0.1:8080/api/health; echo
bash /tmp/_smoke_preview_udp.sh
