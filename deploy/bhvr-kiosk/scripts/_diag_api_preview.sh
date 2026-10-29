#!/bin/bash
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74

cp /tmp/bhvr-kiosk-deploy/preview.py /home/admin/bhvr-kiosk/app/preview.py
cp /tmp/bhvr-kiosk-deploy/index.html /home/admin/bhvr-kiosk/app/templates/index.html

# Ensure leftover encoders are dead
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'pkill -9 rpicam-vid; pkill -9 ffmpeg; sleep 1; pgrep -af rpicam||echo clear' || true
curl -s -X POST 'http://127.0.0.1:8080/api/preview/stop' >/dev/null || true

pkill -f 'uvicorn app.main' 2>/dev/null || true
sleep 1
cd /home/admin/bhvr-kiosk
: >/tmp/kiosk-web.log
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 3

python3 - <<'PY'
from app.preview import cam_live_ssh_mpegts_remote, preview_settings
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("config.yaml").read_text())
s = preview_settings(cfg)
print("transport", s.transport)
print("remote:\n", cam_live_ssh_mpegts_remote(s))
PY

echo "=== API 20s with verbose curl ==="
rm -f /tmp/api_prev.ts
timeout 20 curl -v -sSN -o /tmp/api_prev.ts 'http://127.0.0.1:8080/api/preview/bhvr-cam0' 2>/tmp/api_curl.err || echo curl_exit=$?
echo "--- curl err ---"; head -40 /tmp/api_curl.err
echo "--- size ---"; ls -la /tmp/api_prev.ts 2>/dev/null || echo NO
echo "--- kiosk log ---"; tail -40 /tmp/kiosk-web.log
echo "--- preview log ---"; tail -40 /tmp/bhvr-preview-bhvr-cam0.log 2>/dev/null || echo none
pgrep -af 'ssh|uvicorn|ffmpeg|rpicam' | head -20
curl -s -X POST 'http://127.0.0.1:8080/api/preview/stop?cam_id=bhvr-cam0'; echo
