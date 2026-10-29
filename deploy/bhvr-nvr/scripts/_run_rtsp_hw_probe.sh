#!/bin/bash
set -euo pipefail
URL="rtsp://127.0.0.1:8554/${CAM_ID:-bhvr-cam0}"
echo "=== hwaccels ==="
ffmpeg -hide_banner -hwaccels || true
echo "=== decode hwaccel auto 12s ==="
timeout 12 ffmpeg -hide_banner -loglevel info \
  -hwaccel auto -rtsp_transport tcp -i "$URL" -an -f null - \
  2>/tmp/litmus_rtsp_hw.log || true
grep -E 'hwaccel|Stream #0|Error|frame=' /tmp/litmus_rtsp_hw.log | tail -25 || true
python3 - <<'PY'
import re
from pathlib import Path
t = Path("/tmp/litmus_rtsp_hw.log").read_text(errors="replace")
fps = re.findall(r"fps=\s*([0-9.]+)", t)
fr = re.findall(r"frame=\s*(\d+)", t)
sp = re.findall(r"speed=\s*([0-9.]+)x", t)
print("fps_tail", fps[-8:] if fps else None)
print("frames_tail", fr[-5:] if fr else None)
print("speed_tail", sp[-5:] if sp else None)
if fr:
    print("last_frame", fr[-1])
# Did it claim a hwaccel?
for line in t.splitlines():
    if "hwaccel" in line.lower() or "v4l2" in line.lower() or "drm" in line.lower():
        print("hint:", line[:160])
PY
echo "=== copy-ts only (no decode) 12s — ingest rate ==="
timeout 12 ffmpeg -hide_banner -loglevel info \
  -rtsp_transport tcp -i "$URL" -c copy -f null - \
  2>/tmp/litmus_rtsp_copy.log || true
python3 - <<'PY'
import re
from pathlib import Path
t = Path("/tmp/litmus_rtsp_copy.log").read_text(errors="replace")
fps = re.findall(r"fps=\s*([0-9.]+)", t)
fr = re.findall(r"frame=\s*(\d+)", t)
sp = re.findall(r"speed=\s*([0-9.]+)x", t)
print("COPY fps_tail", fps[-8:] if fps else None)
print("COPY frames_tail", fr[-5:] if fr else None)
print("COPY speed_tail", sp[-5:] if sp else None)
if fr:
    print("COPY last_frame", fr[-1])
PY
tail -5 /tmp/litmus_rtsp_copy.log || true
