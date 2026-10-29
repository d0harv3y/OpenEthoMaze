#!/bin/bash
set -uo pipefail
echo "=== health ==="
curl -s --max-time 3 http://127.0.0.1:8080/api/health; echo
echo "=== cams ==="
curl -s --max-time 3 http://127.0.0.1:8080/api/cams; echo
echo "=== procs ==="
pgrep -af 'uvicorn|ffmpeg|rpicam|live_udp|ssh.*235' || true
echo "=== preview logs ==="
ls -la /tmp/bhvr-preview* 2>/dev/null || echo none
for f in /tmp/bhvr-preview*; do
  [ -f "$f" ] || continue
  echo "--- $f ---"
  tail -40 "$f"
done
echo "=== kiosk log tail ==="
tail -40 /tmp/kiosk-web.log 2>/dev/null || true
