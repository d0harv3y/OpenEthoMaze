#!/bin/bash
# Deploy UDP race fix, flip transport=udp, restart, hit preview API briefly.
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
SRC=/tmp/bhvr-kiosk-deploy

cp "$SRC/main.py" /home/admin/bhvr-kiosk/app/main.py
cp "$SRC/config.example.yaml" /home/admin/bhvr-kiosk/config.example.yaml 2>/dev/null || true

python3 - <<'PY'
from pathlib import Path
import yaml
p = Path("/home/admin/bhvr-kiosk/config.yaml")
cfg = yaml.safe_load(p.read_text()) or {}
rec = cfg.setdefault("record", {})
rec["soft_fps"] = 10
rec.setdefault("bitrate_kbps", 1200)
cfg["record"] = rec
prev = cfg.setdefault("preview", {})
prev["transport"] = "udp"
prev["fps_idle"] = 10
prev.setdefault("udp_port", 15550)
prev.setdefault("nvr_host", "10.248.238.22")
prev.setdefault("bitrate_kbps", 800)
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
print("transport", prev["transport"], "soft_fps", rec["soft_fps"])
PY

pkill -f 'uvicorn app.main' 2>/dev/null || true
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'pkill -INT rpicam-vid; pkill -f live_udp; pkill -f "ffmpeg.*udp"; true' || true
sleep 1

cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2
curl -s http://127.0.0.1:8080/api/health
echo

# Roster may need a moment; try preview for bhvr-cam0
CAM_ID=bhvr-cam0
echo "=== preview UDP stream (8s) ==="
timeout 8 curl -sS -o /tmp/preview_udp.ts -w "http=%{http_code} bytes=%{size_download}\n" \
  "http://127.0.0.1:8080/api/preview/${CAM_ID}/stream" || true
ls -la /tmp/preview_udp.ts 2>/dev/null || true
ffprobe -v error -show_entries stream=codec_name,width,height -of default=nw=1 /tmp/preview_udp.ts 2>&1 | head -10 || true
tail -20 /tmp/bhvr-preview-${CAM_ID}.log 2>/dev/null || true
curl -s -X POST "http://127.0.0.1:8080/api/preview/stop?cam_id=${CAM_ID}" || true
echo
