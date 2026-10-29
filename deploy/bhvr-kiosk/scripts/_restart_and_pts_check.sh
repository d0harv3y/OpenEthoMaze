#!/bin/bash
set -uo pipefail
pkill -f 'uvicorn app.main' 2>/dev/null || true
sleep 1
cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 3
curl -s --max-time 3 http://127.0.0.1:8080/api/health || echo HEALTH_FAIL
echo
pgrep -af 'uvicorn app.main' || echo NO_UVICORN

KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" 'pkill -9 rpicam-vid; pkill -9 ffmpeg; true' || true
sleep 1

rm -f /tmp/api_wc.ts
timeout 12 curl -sSN -o /tmp/api_wc.ts 'http://127.0.0.1:8080/api/preview/bhvr-cam0' || echo curl_exit=$?
ls -la /tmp/api_wc.ts 2>/dev/null || echo NO_TS
ffprobe -v error -show_entries packet=pts_time -of csv=p=0 /tmp/api_wc.ts 2>/dev/null | head -5
ffprobe -v warning -i /tmp/api_wc.ts 2>&1 | grep unset || echo 'no unset-timestamps warning'
curl -s -X POST 'http://127.0.0.1:8080/api/preview/stop?cam_id=bhvr-cam0' || true
echo
curl -s http://127.0.0.1:8080/ | grep -o 'const PREVIEW_TRANSPORT = [^;]*'
echo
