#!/usr/bin/env python3
from pathlib import Path
import statistics
import sys

out = Path(sys.argv[1] if len(sys.argv) > 1 else "/media/admin/random/bhvr-tests/20260925T214404Z_720p30")
lines = []
for line in (out / "timestamps.pts").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#"):
        lines.append(float(line))
# rpicam --save-pts format v2: milliseconds
span_s = (lines[-1] - lines[0]) / 1000.0
fps = (len(lines) - 1) / span_s
dts = [lines[i + 1] - lines[i] for i in range(len(lines) - 1)]
vid = out / "video.mp4"
print(f"OUT={out}")
print(f"pts_frames={len(lines)}")
print(f"video_bytes={vid.stat().st_size}")
print(f"span_s={span_s:.3f}")
print(f"achieved_fps={fps:.2f}")
print("requested_fps=30")
print("requested_profile=720p30 1280x720")
print(f"dt_ms_median={statistics.median(dts):.2f}")
print(f"dt_ms_p95={sorted(dts)[int(0.95 * (len(dts) - 1))]:.2f}")
print(f"dt_ms_max={max(dts):.2f}")
doubles = sum(1 for d in dts if d > 50)
print(f"intervals_gt_50ms={doubles} ({100 * doubles / len(dts):.1f}%)")
