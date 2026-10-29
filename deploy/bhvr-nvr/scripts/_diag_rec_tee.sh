#!/bin/bash
set -eu
echo "=== ffmpeg on NVR ==="
command -v ffmpeg
ffmpeg -version 2>&1 | head -1
echo "=== rec-tee logs ==="
ls -lt /tmp/bhvr-preview-*-rec.log 2>/dev/null | head -8 || echo none
for f in /tmp/bhvr-preview-bhvr-cam0-rec.log /tmp/bhvr-preview-bhvr-cam1-rec.log \
         /tmp/bhvr-preview-bhvr-cam2-rec.log /tmp/bhvr-preview-bhvr-cam3-rec.log; do
  if [[ -f "$f" ]]; then
    echo "-- $f ($(wc -c <"$f") B) --"
    tail -30 "$f"
  fi
done
echo "=== kiosk log (rec-tee / preview) ==="
grep -E 'rec-tee|promote:|409|ffmpeg exited' /tmp/kiosk-web.log 2>/dev/null | tail -50 || true
echo "=== health ==="
curl -sS -m 3 http://127.0.0.1:8080/api/health || true
echo
