#!/bin/bash
set -uo pipefail
ROOT=/media/admin/random/bhvr/sub-test2
ls -la "$ROOT"
echo ===
latest=$(ls -1dt "$ROOT"/ses-* 2>/dev/null | head -1)
echo "latest=$latest"
[ -n "$latest" ] || exit 0
ls -lah "$latest"
echo ---meta---
cat "$latest/meta.json" 2>/dev/null || true
echo ---fps---
cat "$latest"/*_fps.json 2>/dev/null || true
echo ---stop---
cat "$latest/stop_log.json" 2>/dev/null || true
echo ---probe---
for f in "$latest"/*.h264 "$latest"/*.mp4; do
  [ -f "$f" ] || continue
  echo "FILE $f ($(stat -c%s "$f") bytes)"
  ffprobe -v error -show_entries format=duration,size,bit_rate \
    -show_entries stream=codec_name,width,height,avg_frame_rate \
    -of default=nw=1 "$f" 2>&1 | head -20
done
echo ---capture log tail---
tail -40 "$latest"/*_capture.log 2>/dev/null || true
