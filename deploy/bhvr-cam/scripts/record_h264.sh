#!/bin/bash
# Profiled H.264 capture for bhvr-cam (OV5647 / rpicam-vid).
# Writes annex-B elementary stream (.h264) — not a fake .mp4. Remux on NVR/PC:
#   ffmpeg -framerate 30 -i video.h264 -c copy video.mp4
set -euo pipefail

PROFILE="${PROFILE:-720p30}"
OUT="${OUT:-/data/bhvr/current/video.h264}"
PTS="${PTS:-/data/bhvr/current/timestamps.pts}"
DURATION="${DURATION:-0}"   # 0 = until SIGINT; else rpicam timeout ms

# Back-compat: if caller still passes .mp4, coerce to .h264 (rpicam --codec h264
# does not write a real MP4 container).
case "$OUT" in
  *.mp4) OUT="${OUT%.mp4}.h264" ;;
esac

case "$PROFILE" in
  720p30) W=1280; H=720; FPS=30 ;;
  720p20) W=1280; H=720; FPS=20 ;;
  480p30) W=640;  H=480; FPS=30 ;;
  *) echo "unknown PROFILE=$PROFILE (720p30|720p20|480p30)" >&2; exit 1 ;;
esac

mkdir -p "$(dirname "$OUT")"
ARGS=(-n --width "$W" --height "$H" --framerate "$FPS" --codec h264 --inline --denoise cdn_off --save-pts "$PTS" -o "$OUT")
if [[ "$DURATION" != "0" ]]; then
  ARGS+=(-t "$DURATION")
else
  ARGS+=(-t 0)
fi

exec rpicam-vid "${ARGS[@]}"
