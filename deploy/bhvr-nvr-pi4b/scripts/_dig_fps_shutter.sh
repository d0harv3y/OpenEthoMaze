#!/bin/bash
# Run ON cam1 — does fixed shutter unlock 720p30?
set -euxo pipefail

pts_fps() {
  python3 - "$1" <<'PY'
import sys, statistics
from pathlib import Path
vals=[]
for line in Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines():
    line=line.strip()
    if not line or line.startswith("#"):
        continue
    for p in line.replace(","," ").split():
        try:
            vals.append(float(p)); break
        except ValueError:
            pass
if len(vals)<2:
    print("fps=NA"); raise SystemExit
dts=[vals[i+1]-vals[i] for i in range(len(vals)-1) if vals[i+1]>vals[i]]
med=statistics.median(dts)
span=vals[-1]-vals[0]
span_s=span/1e6 if med>1000 else (span/1e3 if med>1 else span)
fps=(len(vals)-1)/span_s if span_s>0 else float("nan")
print(f"frames={len(vals)} med_dt={med:.1f} fps={fps:.2f}")
PY
}

trial() {
  local tag="$1"; shift
  echo "==== $tag ===="
  rm -f "/tmp/sh_${tag}.h264" "/tmp/sh_${tag}.pts" "/tmp/sh_${tag}.log"
  timeout 8 rpicam-vid -n -t 5000 "$@" --codec h264 --inline --flush --bitrate 2500000 \
    --denoise cdn_off --buffer-count 2 --save-pts "/tmp/sh_${tag}.pts" -o "/tmp/sh_${tag}.h264" \
    >"/tmp/sh_${tag}.log" 2>&1 || true
  pts_fps "/tmp/sh_${tag}.pts"
  grep -E 'Selected sensor|Exposure|FrameDuration' "/tmp/sh_${tag}.log" | head -8 || true
}

# baseline
trial base --width 1280 --height 720 --framerate 30 --intra 30
# fixed shutter 10ms, gain 4
trial sh10g4 --width 1280 --height 720 --framerate 30 --intra 30 --shutter 10000 --gain 4
# shutter 8ms gain 6
trial sh8g6 --width 1280 --height 720 --framerate 30 --intra 30 --shutter 8000 --gain 6
# shutter 15ms (still under 33ms)
trial sh15g4 --width 1280 --height 720 --framerate 30 --intra 30 --shutter 15000 --gain 4
# 1296 mode + short shutter
trial mode_sh --mode 1296:972:10:P --width 1280 --height 720 --framerate 30 --intra 30 --shutter 10000 --gain 4
# 480p short shutter (should hit ~30)
trial c480sh --width 640 --height 480 --framerate 30 --intra 30 --shutter 10000 --gain 4

echo SHUTTER_DIG_DONE
