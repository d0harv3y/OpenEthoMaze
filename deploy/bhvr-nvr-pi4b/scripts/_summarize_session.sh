#!/bin/bash
set -eu
SES="${1:-/media/admin/random/bhvr/sub-test1/ses-20261021T190957Z}"
echo "=== meta ==="
cat "$SES/meta.json"
echo
echo "=== sizes ==="
ls -la "$SES"/*.ts "$SES"/*_fps.json "$SES"/*_timestamps.pts 2>/dev/null
echo
python3 - <<PY
import json
from pathlib import Path
ses = Path("$SES")
print("=== fps / size table ===")
print(f"{'cam':12} {'ts_MB':>8} {'pts_B':>8} {'ach_fps':>8} {'frames':>8} {'span_s':>8}")
for cam in ["bhvr-cam0","bhvr-cam1","bhvr-cam2","bhvr-cam3"]:
    ts = ses / f"{cam}_video.ts"
    pts = ses / f"{cam}_timestamps.pts"
    fpsj = ses / f"{cam}_fps.json"
    ts_mb = ts.stat().st_size / 1e6 if ts.is_file() else 0
    pts_b = pts.stat().st_size if pts.is_file() else 0
    ach = frames = span = "—"
    if fpsj.is_file():
        d = json.loads(fpsj.read_text())
        ach = d.get("achieved_fps")
        frames = d.get("pts_frames")
        span = d.get("span_s")
    print(f"{cam:12} {ts_mb:8.2f} {pts_b:8} {str(ach):>8} {str(frames):>8} {str(span):>8}")
print()
print("=== stop_log ===")
sl = ses / "stop_log.json"
if sl.is_file():
    for line in json.loads(sl.read_text()):
        print(line)
PY
