#!/bin/bash
set -euo pipefail
CAM_ID="${CAM_ID:-bhvr-cam0}"
DUR="${DURATION_S:-12}"
curl -sS -m 90 -X POST "http://127.0.0.1:8080/api/preview/${CAM_ID}/whep/start" || true
echo
sleep 6
ssh -i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes \
  admin@192.168.7.41 'pgrep -af rpicam-vid' || true
# wait RTSP
for i in $(seq 1 15); do
  ffprobe -rtsp_transport tcp -v error -select_streams v:0 \
    -show_entries stream=width,height,r_frame_rate -of csv=p=0 \
    "rtsp://127.0.0.1:8554/${CAM_ID}" 2>/dev/null && break
  sleep 1
done
timeout "$DUR" ffmpeg -hide_banner -loglevel info -rtsp_transport tcp \
  -i "rtsp://127.0.0.1:8554/${CAM_ID}" -c copy -f null - 2>/tmp/buf_copy.log || true
python3 - <<PY
import re
from pathlib import Path
t = Path("/tmp/buf_copy.log").read_text(errors="replace")
fps = re.findall(r"fps=\s*([0-9.]+)", t)
fr = re.findall(r"frame=\s*(\d+)", t)
sp = re.findall(r"speed=\s*([0-9.]+)x", t)
dur = float("$DUR")
print("fps_tail", fps[-8:] if fps else None)
print("frames_tail", fr[-4:] if fr else None)
print("speed_tail", sp[-4:] if sp else None)
if fr:
    wall = int(fr[-1]) / dur
    print("wall_fps", round(wall, 2))
    print("RESULT", "PASS_near_30" if wall >= 25 else "BELOW_30")
else:
    print("RESULT FAIL")
PY
