#!/bin/bash
set -u
run_one() {
  W=$1; H=$2; REQ=$3; TAG=$4
  OUT=/tmp/fps_${TAG}.h264
  PTS=/tmp/fps_${TAG}.pts
  LOG=/tmp/fps_${TAG}.log
  rm -f "$OUT" "$PTS" "$LOG"
  echo "=== ${W}x${H} request ${REQ}fps (${TAG}) ==="
  t0=$(date +%s.%N)
  rpicam-vid -n -t 10000 --width "$W" --height "$H" --framerate "$REQ" \
      --codec h264 --bitrate 4000000 --inline --denoise cdn_off \
      --save-pts "$PTS" -o "$OUT" -v 1 >"$LOG" 2>&1 || true
  t1=$(date +%s.%N)
  python3 -c "print(f'wall_s={float('$t1')-float('$t0'):.2f}')"
  python3 - "$PTS" "$OUT" "$LOG" <<'PY'
import sys
from pathlib import Path
pts_p, out_p, log_p = map(Path, sys.argv[1:])
log = log_p.read_text(errors="replace") if log_p.exists() else ""
tail = " | ".join(log.strip().splitlines()[-5:])
print("log_tail:", tail)
if not pts_p.exists():
    print("NO_PTS")
    raise SystemExit
lines = [l.strip() for l in pts_p.read_text().splitlines() if l.strip() and not l.startswith("#")]
ts = [float(x) for x in lines]
print(f"frames={len(ts)}")
if len(ts) >= 2:
    dur_ms = ts[-1] - ts[0]
    fps = (len(ts) - 1) * 1000.0 / dur_ms if dur_ms > 0 else float("nan")
    dts = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    dts.sort()
    mid = dts[len(dts) // 2]
    p95 = dts[int(0.95 * (len(dts) - 1))]
    print(f"span_s={dur_ms/1000:.3f} realized_fps={fps:.2f}")
    print(f"dt_ms median={mid:.2f} p95={p95:.2f} min={dts[0]:.2f} max={dts[-1]:.2f}")
sz = out_p.stat().st_size if out_p.exists() else 0
print(f"file_MB={sz/1e6:.2f}")
PY
  echo
}

echo "host=$(hostname) model=$(tr -d '\0' </proc/device-tree/model)"
rpicam-hello --list-cameras 2>&1 | head -n 20
echo
echo "warmup..."
rpicam-vid -n -t 2000 --width 640 --height 480 --framerate 30 --codec h264 -o /tmp/warmup.h264 >/dev/null 2>&1 || true

run_one 640 480 30 640_30
run_one 640 480 60 640_60
run_one 1280 720 20 720_20
run_one 1280 720 30 720_30
run_one 1296 972 30 972_30
run_one 1920 1080 30 1080_30

echo DONE
