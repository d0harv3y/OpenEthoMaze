#!/bin/bash
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
NVR=10.248.238.22
PORT=15550
CAM_ID=bhvr-cam0

cp /tmp/bhvr-kiosk-deploy/main.py /home/admin/bhvr-kiosk/app/main.py
cp /tmp/bhvr-kiosk-deploy/preview.py /home/admin/bhvr-kiosk/app/preview.py

pkill -f 'uvicorn app.main' 2>/dev/null || true
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'pkill -INT rpicam-vid; pkill -f live_udp; pkill -f "ffmpeg.*udp"; true' || true
pkill -f "ffmpeg.*${PORT}" 2>/dev/null || true
sleep 1

# Manual: cam first, then ffmpeg (mirrors app order)
echo "=== manual cam-then-ffmpeg ==="
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  "nohup /home/admin/bhvr-cam/scripts/live_udp_mpegts.sh ${NVR} ${PORT} 640 480 10 800 2 >/tmp/live_udp.log 2>&1 &"
sleep 4
rm -f /tmp/manual_udp.ts
timeout 8 ffmpeg -hide_banner -loglevel warning \
  -fflags nobuffer+genpts+discardcorrupt -flags low_delay \
  -probesize 200000 -analyzeduration 1000000 \
  -f mpegts -i "udp://0.0.0.0:${PORT}?overrun_nonfatal=1&fifo_size=50000000&reuse=1&timeout=15000000" \
  -c copy -f mpegts -y /tmp/manual_udp.ts >/tmp/manual_ff.log 2>&1 || true
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'pkill -INT rpicam-vid; pkill -f live_udp; pkill -f "ffmpeg.*udp"; true' || true
ls -la /tmp/manual_udp.ts 2>/dev/null || echo NO_FILE
ffprobe -v error -show_entries stream=codec_name,width,height -of default=nw=1 /tmp/manual_udp.ts 2>&1 | head -10
echo "--- manual ff ---"; tail -15 /tmp/manual_ff.log

cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2
curl -s http://127.0.0.1:8080/api/health; echo

bash /tmp/_smoke_preview_udp.sh
