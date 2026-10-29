#!/bin/bash
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
SRC=/tmp/bhvr-kiosk-deploy

cp "$SRC/preview.py" /home/admin/bhvr-kiosk/app/preview.py
cp "$SRC/index.html" /home/admin/bhvr-kiosk/app/templates/index.html
scp -i "$KEY" -o BatchMode=yes "$SRC/live_udp_mpegts.sh" \
  "admin@${CAM}:~/bhvr-cam/scripts/live_udp_mpegts.sh"
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'sed -i "s/\r$//" ~/bhvr-cam/scripts/live_udp_mpegts.sh; chmod +x ~/bhvr-cam/scripts/live_udp_mpegts.sh; pkill -INT rpicam-vid; pkill -f ffmpeg; true' || true

pkill -f 'uvicorn app.main' 2>/dev/null || true
sleep 1
cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2

echo "=== direct 12s (no -framerate on ffmpeg -i) ==="
timeout 12 ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'pkill -INT rpicam-vid 2>/dev/null; sleep 0.3; stdbuf -o0 rpicam-vid -n -t 0 --width 640 --height 480 --framerate 10 --codec h264 --inline --intra 10 --flush --bitrate 800000 --denoise cdn_off --buffer-count 2 -o - | ffmpeg -hide_banner -loglevel warning -nostats -fflags nobuffer+genpts+flush_packets -flags low_delay -avioflags direct -f h264 -i pipe:0 -c copy -muxdelay 0 -muxpreload 0 -flush_packets 1 -f mpegts pipe:1' \
  > /tmp/direct_ssh.ts 2>/tmp/direct_ssh.err || true
ls -la /tmp/direct_ssh.ts
wc -c /tmp/direct_ssh.ts
ffprobe -v error -show_entries stream=codec_name,width,height -of default=nw=1 /tmp/direct_ssh.ts 2>&1 | head -8
tail -5 /tmp/direct_ssh.err

echo "=== API 12s ==="
rm -f /tmp/api_prev.ts
timeout 12 curl -sSN -o /tmp/api_prev.ts 'http://127.0.0.1:8080/api/preview/bhvr-cam0' || echo curl_exit=$?
ls -la /tmp/api_prev.ts 2>/dev/null || echo NO
ffprobe -v error -show_entries stream=codec_name,width,height -of default=nw=1 /tmp/api_prev.ts 2>&1 | head -8
curl -s -X POST 'http://127.0.0.1:8080/api/preview/stop?cam_id=bhvr-cam0'; echo
curl -s http://127.0.0.1:8080/api/health; echo
