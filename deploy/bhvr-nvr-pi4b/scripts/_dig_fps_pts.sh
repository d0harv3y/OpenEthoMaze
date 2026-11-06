#!/bin/bash
# Run ON cam1 — achieved fps from timestamps.pts (science truth method)
set -euxo pipefail

pts_fps() {
  local pts="$1"
  python3 - "$pts" <<'PY'
import sys
from pathlib import Path
raw = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").strip().splitlines()
# rpicam pts file: often "# timecode format..." then lines of integers (µs) or "frame pts"
vals = []
for line in raw:
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    parts = line.replace(",", " ").split()
    for p in parts:
        try:
            vals.append(float(p))
            break
        except ValueError:
            continue
if len(vals) < 2:
    print(f"pts_frames={len(vals)} fps=NA")
    raise SystemExit(0)
# detect unit: if values look like µs spans (diff ~3e4) or ms
span = vals[-1] - vals[0]
n = len(vals)
# assume microseconds if median dt > 1000
import statistics
dts = [vals[i+1]-vals[i] for i in range(len(vals)-1) if vals[i+1]>vals[i]]
med = statistics.median(dts) if dts else 0
if med > 1000:  # µs
    span_s = span / 1e6
elif med > 1:  # ms
    span_s = span / 1e3
else:
    span_s = span
fps = (n - 1) / span_s if span_s > 0 else float("nan")
print(f"pts_frames={n} span_s={span_s:.3f} med_dt={med:.1f} fps={fps:.2f}")
PY
}

run_one() {
  local tag="$1"
  shift
  echo "==== $tag ===="
  rm -f "/tmp/fps_${tag}.h264" "/tmp/fps_${tag}.pts" "/tmp/fps_${tag}.log"
  # shellcheck disable=SC2068
  timeout 8 rpicam-vid -n -t 5000 "$@" --codec h264 --inline --flush --bitrate 2500000 \
    --denoise cdn_off --buffer-count 2 \
    --save-pts "/tmp/fps_${tag}.pts" -o "/tmp/fps_${tag}.h264" \
    >"/tmp/fps_${tag}.log" 2>&1 || true
  wc -c "/tmp/fps_${tag}.h264" "/tmp/fps_${tag}.pts"
  pts_fps "/tmp/fps_${tag}.pts"
  grep -E 'Selected sensor|Mode selection' "/tmp/fps_${tag}.log" | head -5 || true
}

run_one a30 --width 1280 --height 720 --framerate 30 --intra 30
run_one b30mode --mode 1296:972:10:P --width 1280 --height 720 --framerate 30 --intra 30
run_one c480 --width 640 --height 480 --framerate 30 --intra 30
run_one d15 --width 1280 --height 720 --framerate 15 --intra 15
run_one e30buf6 --width 1280 --height 720 --framerate 30 --intra 30 --buffer-count 6
# override last buffer-count in run_one - need special case
rm -f /tmp/fps_e30buf6.h264 /tmp/fps_e30buf6.pts /tmp/fps_e30buf6.log
timeout 8 rpicam-vid -n -t 5000 --width 1280 --height 720 --framerate 30 --codec h264 --inline --intra 30 --flush --bitrate 2500000 --denoise cdn_off --buffer-count 6 --save-pts /tmp/fps_e30buf6.pts -o /tmp/fps_e30buf6.h264 >/tmp/fps_e30buf6.log 2>&1 || true
echo "==== e30buf6 ===="
wc -c /tmp/fps_e30buf6.h264 /tmp/fps_e30buf6.pts
pts_fps /tmp/fps_e30buf6.pts

run_one f1080 --width 1920 --height 1080 --framerate 30 --intra 30

echo PTS_DIG_DONE
