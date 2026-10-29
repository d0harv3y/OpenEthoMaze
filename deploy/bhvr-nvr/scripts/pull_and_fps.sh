#!/bin/bash
set -euo pipefail
KEY="$HOME/.ssh/id_ed25519_bhvr"
CAM=admin@10.248.235.74
OUT="/media/admin/random/bhvr-tests/$(date -u +%Y%m%dT%H%M%SZ)_720p30"
mkdir -p "$OUT"
RSH="ssh -i $KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
rsync -avz -e "$RSH" \
  "$CAM:bhvr-current/video.mp4" \
  "$CAM:bhvr-current/timestamps.pts" \
  "$OUT/"
ls -la "$OUT"
python3 - "$OUT" <<'PY'
import statistics, sys
from pathlib import Path
out = Path(sys.argv[1])
pts = out / "timestamps.pts"
vid = out / "video.mp4"
lines = [l.strip() for l in pts.read_text().splitlines() if l.strip()]
print(f"pts_frames={len(lines)}")
print(f"video_bytes={vid.stat().st_size}")
first = float(lines[0]); last = float(lines[-1])
dt_us = last - first
dt_s = dt_us / 1e6 if abs(dt_us) > 1000 else float(dt_us)
fps = (len(lines) - 1) / dt_s if dt_s > 0 else float("nan")
print(f"span_s={dt_s:.3f}")
print(f"achieved_fps={fps:.2f}")
print("requested_fps=30")
print("requested_profile=720p30")
ts = [float(x) for x in lines]
ts_ms = [t / 1000.0 for t in ts] if ts[-1] - ts[0] > 1e6 else [t * 1000.0 for t in ts]
dts = [ts_ms[i + 1] - ts_ms[i] for i in range(len(ts_ms) - 1)]
print(f"dt_ms_median={statistics.median(dts):.2f}")
print(f"dt_ms_p95={sorted(dts)[int(0.95 * (len(dts) - 1))]:.2f}")
print(f"dt_ms_max={max(dts):.2f}")
print(f"OUT={out}")
PY
