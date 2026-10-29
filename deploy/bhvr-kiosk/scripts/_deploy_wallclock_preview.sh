#!/bin/bash
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
SRC=/tmp/bhvr-kiosk-deploy

cp "$SRC/preview.py" /home/admin/bhvr-kiosk/app/preview.py
cp "$SRC/index.html" /home/admin/bhvr-kiosk/app/templates/index.html
scp -i "$KEY" -o BatchMode=yes "$SRC/live_udp_mpegts.sh" \
  "admin@${CAM}:~/bhvr-cam/scripts/live_udp_mpegts.sh"
scp -i "$KEY" -o BatchMode=yes "$SRC/announce_mqtt.py" \
  "admin@${CAM}:~/bhvr-cam/scripts/announce_mqtt.py" 2>/dev/null || true
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'sed -i "s/\r$//" ~/bhvr-cam/scripts/live_udp_mpegts.sh; chmod +x ~/bhvr-cam/scripts/live_udp_mpegts.sh; python3 ~/bhvr-cam/scripts/announce_mqtt.py; pkill -9 rpicam-vid; pkill -9 ffmpeg; true' || true

python3 - <<'PY'
from pathlib import Path
import yaml
p = Path("/home/admin/bhvr-kiosk/config.yaml")
cfg = yaml.safe_load(p.read_text()) or {}
prev = cfg.setdefault("preview", {})
prev["transport"] = "mpegts"
prev["fps_idle"] = 10
prev["buffer_count"] = 2
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
print("preview", {k: prev[k] for k in ("transport", "fps_idle", "buffer_count")})
PY

pkill -f 'uvicorn app.main' 2>/dev/null || true
sleep 1
cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2
curl -s http://127.0.0.1:8080/api/health; echo
curl -s http://127.0.0.1:8080/ | grep -oE 'const PREVIEW_TRANSPORT = [^;]+|hasAudio: [^,]+|liveBufferLatencyChasing: [^,]+'
echo
rm -f /tmp/api_wc.ts
timeout 10 curl -sSN -o /tmp/api_wc.ts 'http://127.0.0.1:8080/api/preview/bhvr-cam0' || true
ls -la /tmp/api_wc.ts
ffprobe -v error -show_entries packet=pts_time -of csv=p=0 /tmp/api_wc.ts 2>/dev/null | head -5
ffprobe -v warning -i /tmp/api_wc.ts 2>&1 | grep -E 'unset|Stream' | head -6 || true
curl -s -X POST 'http://127.0.0.1:8080/api/preview/stop?cam_id=bhvr-cam0'; echo
