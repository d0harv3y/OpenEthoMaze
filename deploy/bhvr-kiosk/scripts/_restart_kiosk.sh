#!/bin/bash
set -uo pipefail
pkill -9 -f 'uvicorn app.main' 2>/dev/null || true
sleep 1
cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2
pgrep -af 'uvicorn app.main' || echo NO_UVICORN
curl -s --max-time 3 http://127.0.0.1:8080/api/health || echo HEALTH_FAIL
echo
