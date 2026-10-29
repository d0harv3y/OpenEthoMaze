#!/bin/bash
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
SRC=/tmp/bhvr-kiosk-deploy

cp "$SRC/preview.py" /home/admin/bhvr-kiosk/app/preview.py
cp "$SRC/index.html" /home/admin/bhvr-kiosk/app/templates/index.html

python3 - <<'PY'
from pathlib import Path
import yaml
p = Path("/home/admin/bhvr-kiosk/config.yaml")
cfg = yaml.safe_load(p.read_text()) or {}
prev = cfg.setdefault("preview", {})
prev["transport"] = "mpegts"  # restore known-good focus live; UDP path kept for retry
prev["fps_idle"] = 10
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
print("transport", prev["transport"])
PY

scp -i "$KEY" -o BatchMode=yes "$SRC/announce_mqtt.py" \
  "admin@${CAM}:~/bhvr-cam/scripts/announce_mqtt.py"
scp -i "$KEY" -o BatchMode=yes "$SRC/live_udp_mpegts.sh" \
  "admin@${CAM}:~/bhvr-cam/scripts/live_udp_mpegts.sh"
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'sed -i "s/\r$//" ~/bhvr-cam/scripts/live_udp_mpegts.sh; chmod +x ~/bhvr-cam/scripts/live_udp_mpegts.sh; python3 ~/bhvr-cam/scripts/announce_mqtt.py'

pkill -f 'uvicorn app.main' 2>/dev/null || true
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'pkill -INT rpicam-vid; pkill -f "ffmpeg.*udp"; true' || true
sleep 1
cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2
curl -s http://127.0.0.1:8080/api/health; echo

rm -f /tmp/live_ssh.ts
timeout 8 curl -sSN -o /tmp/live_ssh.ts 'http://127.0.0.1:8080/api/preview/bhvr-cam0' || true
ls -la /tmp/live_ssh.ts 2>/dev/null || echo NO_TS
ffprobe -v error -show_entries stream=codec_name,width,height -of default=nw=1 /tmp/live_ssh.ts 2>&1 | head -8
ffprobe -v error -show_entries packet=pts_time -of csv=p=0 /tmp/live_ssh.ts 2>/dev/null | head -3
curl -s -X POST 'http://127.0.0.1:8080/api/preview/stop?cam_id=bhvr-cam0'; echo
echo "page transport hint:" 
curl -s http://127.0.0.1:8080/ | grep -o 'const PREVIEW_TRANSPORT = [^;]*'
