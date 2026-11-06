#!/bin/bash
# Deploy REC/LIVE split badges + capture-stats API to NVR kiosk.
set -euxo pipefail
SRC=/tmp/bhvr-rec-live
DEST="$HOME/bhvr-kiosk"
cp -f "$SRC/capture_stats.py" "$DEST/app/capture_stats.py"
cp -f "$SRC/main.py" "$DEST/app/main.py"
cp -f "$SRC/index.html" "$DEST/app/templates/index.html"
grep -n "capture-stats\|note_capture_bytes\|REC = SSD" "$DEST/app/main.py" "$DEST/app/templates/index.html" | head -20
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
cd "$DEST"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 25); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.4
done
.venv/bin/python -c '
from app.capture_stats import new_capture_byte_stats, note_capture_bytes, snapshot_capture_stats
s = new_capture_byte_stats(now=1.0)
note_capture_bytes(s, 500_000, now=2.0)
note_capture_bytes(s, 500_000, now=3.0)
snap = snapshot_capture_stats(s, soft_fps=30, bitrate_bps=4_000_000, now=3.1)
assert snap["status"] == "ok" and snap["est_fps"] == 30.0, snap
print("capture_stats_ok", snap)
'
curl -sS http://127.0.0.1:8080/api/session/capture-stats; echo
curl -sS http://127.0.0.1:8080/api/health | head -c 400; echo
