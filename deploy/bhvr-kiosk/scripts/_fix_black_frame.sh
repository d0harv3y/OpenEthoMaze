#!/bin/bash
# Deploy black-frame + profile label fixes; restart kiosk; patch cam PROFILE.
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
SRC=/tmp/bhvr-kiosk-deploy

cp "$SRC/main.py" /home/admin/bhvr-kiosk/app/main.py 2>/dev/null || true
cp "$SRC/preview.py" /home/admin/bhvr-kiosk/app/preview.py
cp "$SRC/index.html" /home/admin/bhvr-kiosk/app/templates/index.html

scp -i "$KEY" -o BatchMode=yes "$SRC/live_udp_mpegts.sh" \
  "admin@${CAM}:~/bhvr-cam/scripts/live_udp_mpegts.sh"
scp -i "$KEY" -o BatchMode=yes "$SRC/announce_mqtt.py" \
  "admin@${CAM}:~/bhvr-cam/scripts/announce_mqtt.py"
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" bash -s <<'CAM'
set -e
sed -i 's/\r$//' ~/bhvr-cam/scripts/live_udp_mpegts.sh
chmod +x ~/bhvr-cam/scripts/live_udp_mpegts.sh
# Prefer resolution-only label in MQTT (was 720p30 from firstboot/env).
if [ -f /etc/bhvr-cam.env ]; then
  sudo sed -i 's/^PROFILE=.*/PROFILE=720p/' /etc/bhvr-cam.env 2>/dev/null \
    || sed -i 's/^PROFILE=.*/PROFILE=720p/' /etc/bhvr-cam.env 2>/dev/null || true
fi
grep -E '^PROFILE=' /etc/bhvr-cam.env 2>/dev/null || echo 'PROFILE=(unset, announce default 720p)'
# Re-announce now
python3 ~/bhvr-cam/scripts/announce_mqtt.py || true
pkill -INT rpicam-vid 2>/dev/null || true
pkill -f 'ffmpeg.*udp://' 2>/dev/null || true
CAM

pkill -f 'uvicorn app.main' 2>/dev/null || true
sleep 1
cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2
curl -s http://127.0.0.1:8080/api/health; echo
curl -s http://127.0.0.1:8080/ | grep -o 'liveBufferLatencyChasing: [^,]*'
curl -s http://127.0.0.1:8080/ | grep -o 'hasAudio: [^,]*'

# Quick PTS check on a short UDP grab
rm -f /tmp/live5.ts
timeout 10 curl -sSN -o /tmp/live5.ts 'http://127.0.0.1:8080/api/preview/bhvr-cam0' || true
ls -la /tmp/live5.ts 2>/dev/null || echo NO_TS
ffprobe -v error -show_entries packet=pts_time -of csv=p=0 /tmp/live5.ts 2>/dev/null | head -5
ffprobe -v warning -i /tmp/live5.ts 2>&1 | grep -E 'unset|Duration|Stream|error' | head -10
curl -s -X POST 'http://127.0.0.1:8080/api/preview/stop?cam_id=bhvr-cam0'; echo
