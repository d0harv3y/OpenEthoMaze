#!/bin/bash
# Assumes MediaMTX RTSP up and cam already publishing. Measures decode fps + brief ffplay.
set -euo pipefail
CAM="${CAM_ID:-bhvr-cam0}"
URL="rtsp://127.0.0.1:8554/${CAM}"
DUR="${DURATION_S:-15}"
DISPLAY_ENV="${DISPLAY_ENV:-:0}"

echo "=== wait for RTSP path $CAM ==="
ready=0
for i in $(seq 1 20); do
  if ffprobe -rtsp_transport tcp -v error \
      -select_streams v:0 \
      -show_entries stream=codec_name,width,height,r_frame_rate \
      -of csv=p=0 "$URL" 2>/dev/null; then
    echo "ready_after=${i}s"
    ready=1
    break
  fi
  echo "wait_${i}"
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "FAIL: RTSP path never ready" >&2
  journalctl -u bhvr-mediamtx -n 30 --no-pager || true
  exit 1
fi

FPS_LOG=/tmp/litmus_rtsp_fps2.log
echo "=== ffmpeg decode ${DUR}s ==="
timeout "$DUR" ffmpeg -hide_banner -loglevel info \
  -rtsp_transport tcp -i "$URL" -an -f null - 2>"$FPS_LOG" || true
tail -8 "$FPS_LOG"

python3 - "$FPS_LOG" "$DUR" <<'PY'
import re, sys
from pathlib import Path
t = Path(sys.argv[1]).read_text(errors="replace")
dur = float(sys.argv[2])
fps = re.findall(r"fps=\s*([0-9.]+)", t)
fr = re.findall(r"frame=\s*(\d+)", t)
speed = re.findall(r"speed=\s*([0-9.]+)x", t)
print("fps_tail", fps[-8:] if fps else None)
print("frames_tail", fr[-5:] if fr else None)
print("speed_tail", speed[-5:] if speed else None)
if fr:
    last = int(fr[-1])
    print("last_frame", last, "implied_fps", round(last / dur, 2))
PY

echo "=== on-screen ffplay ${DUR}s max 8s DISPLAY=$DISPLAY_ENV ==="
export DISPLAY="$DISPLAY_ENV"
timeout 8 ffplay -hide_banner -loglevel warning -an -autoexit \
  -window_title "bhvr-rtsp-litmus-$CAM" \
  -rtsp_transport tcp "$URL" >/tmp/litmus_rtsp_ffplay.log 2>&1 || true
echo "ffplay_done"
echo "=== recent RTSP journal ==="
journalctl -u bhvr-mediamtx -n 20 --no-pager | grep -iE 'RTSP|bhvr-cam0' || true
echo "=== done ==="
