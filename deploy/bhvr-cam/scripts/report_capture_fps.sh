#!/bin/bash
# Report achieved FPS from latest /data/bhvr/current capture on this cam.
set -euo pipefail
VID="${1:-/data/bhvr/current/video.mp4}"
PTS="${2:-/data/bhvr/current/timestamps.pts}"
echo "=== files ==="
ls -la "$VID" "$PTS" 2>/dev/null || true
if [[ -f "$PTS" ]]; then
  n=$(wc -l <"$PTS")
  first=$(head -1 "$PTS")
  last=$(tail -1 "$PTS")
  echo "pts_lines=$n first=$first last=$last"
  python3 - <<PY
first=float("$first"); last=float("$last"); n=int("$n")
# rpicam --save-pts is usually microseconds
dt_us = last - first
dt_s = dt_us / 1e6 if abs(dt_us) > 1e3 else dt_us
print(f"span_s={dt_s:.3f}")
if n >= 2 and dt_s > 0:
    print(f"achieved_fps={(n-1)/dt_s:.2f}")
PY
fi
if command -v ffprobe >/dev/null; then
  echo "=== ffprobe ==="
  ffprobe -v error -select_streams v:0 \
    -show_entries stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,duration,codec_name \
    -of default=nw=1 "$VID" || true
else
  echo "ffprobe not installed"
fi
echo "=== requested profiles (bhvr-cam-record) ==="
echo "720p30 -> 1280x720 @ 30 (default / kpMS target)"
echo "720p20 -> 1280x720 @ 20"
echo "480p30 -> 640x480 @ 30"
