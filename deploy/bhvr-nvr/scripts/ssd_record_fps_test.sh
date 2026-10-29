#!/bin/bash
# Timed record on cam (no sudo), pull to SSD on NVR, report achieved FPS.
set -euo pipefail

KEY="${HOME}/.ssh/id_ed25519_bhvr"
CAM_HOST="${1:?cam ip required}"
PROFILE="${2:-720p30}"
SECS="${3:-15}"
SSD_ROOT="${4:-/media/admin/random}"
OUT_DIR="${SSD_ROOT}/bhvr-tests/$(date -u +%Y%m%dT%H%M%SZ)_${PROFILE}"

case "$PROFILE" in
  720p30) W=1280; H=720; FPS=30 ;;
  720p20) W=1280; H=720; FPS=20 ;;
  480p30) W=640;  H=480; FPS=30 ;;
  *) echo "bad profile $PROFILE" >&2; exit 1 ;;
esac

DUR_MS=$((SECS * 1000))
REMOTE="admin@${CAM_HOST}"
SSH=(ssh -i "$KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=25)
RSH="ssh -i ${KEY} -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

echo "cam=$CAM_HOST profile=$PROFILE ${W}x${H}@${FPS} secs=$SECS -> $OUT_DIR"
mkdir -p "$OUT_DIR"

# User-writable paths on cam (avoid broken passwordless sudo)
"${SSH[@]}" "$REMOTE" "mkdir -p ~/bhvr-current && rm -f ~/bhvr-current/video.mp4 ~/bhvr-current/timestamps.pts && \
  nohup rpicam-vid -n -t ${DUR_MS} --width ${W} --height ${H} --framerate ${FPS} \
    --codec h264 --inline --denoise cdn_off \
    --save-pts ~/bhvr-current/timestamps.pts -o ~/bhvr-current/video.mp4 \
    >~/bhvr-current/rpicam.log 2>&1 & echo \$! >~/bhvr-current/pid && cat ~/bhvr-current/pid"

echo "recording ${SECS}s ..."
sleep $((SECS + 5))
"${SSH[@]}" "$REMOTE" "pid=\$(cat ~/bhvr-current/pid 2>/dev/null || true); \
  if [[ -n \"\$pid\" ]] && kill -0 \"\$pid\" 2>/dev/null; then kill -INT \"\$pid\" 2>/dev/null || true; sleep 2; fi; \
  ls -la ~/bhvr-current/; tail -5 ~/bhvr-current/rpicam.log 2>/dev/null || true"

rsync -avz -e "$RSH" \
  "${REMOTE}:bhvr-current/video.mp4" \
  "${REMOTE}:bhvr-current/timestamps.pts" \
  "${REMOTE}:bhvr-current/rpicam.log" \
  "$OUT_DIR/"

VID="$OUT_DIR/video.mp4"
PTS="$OUT_DIR/timestamps.pts"
echo "=== pulled ==="
ls -la "$VID" "$PTS"

python3 - <<PY
from pathlib import Path
import statistics
pts = Path("$PTS")
vid = Path("$VID")
lines = [l.strip() for l in pts.read_text().splitlines() if l.strip()]
print(f"pts_frames={len(lines)}")
print(f"video_bytes={vid.stat().st_size}")
if len(lines) < 2:
    print("achieved_fps=NA")
    raise SystemExit(1)
first = float(lines[0]); last = float(lines[-1])
dt_us = last - first
dt_s = dt_us / 1e6 if abs(dt_us) > 1000 else float(dt_us)
fps = (len(lines) - 1) / dt_s if dt_s > 0 else float("nan")
print(f"span_s={dt_s:.3f}")
print(f"achieved_fps={fps:.2f}")
print(f"requested_fps=$FPS")
print(f"requested_profile=$PROFILE")
ts = [float(x) for x in lines]
if ts[-1] - ts[0] > 1e6:
    ts_ms = [t / 1000.0 for t in ts]
else:
    ts_ms = [t * 1000.0 for t in ts]
dts = [ts_ms[i+1] - ts_ms[i] for i in range(len(ts_ms) - 1)]
print(f"dt_ms_median={statistics.median(dts):.2f}")
print(f"dt_ms_p95={sorted(dts)[int(0.95 * (len(dts) - 1))]:.2f}")
print(f"dt_ms_max={max(dts):.2f}")
PY

echo "OUT_DIR=$OUT_DIR"
