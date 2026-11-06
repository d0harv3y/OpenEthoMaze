#!/bin/bash
# Run ON cam1 — CPU during 720p30 encode + framerate 20 trial
set -euxo pipefail
pts_fps() {
  python3 - "$1" <<'PY'
import sys, statistics
from pathlib import Path
vals=[]
for line in Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines():
    line=line.strip()
    if not line or line.startswith("#"): continue
    for p in line.replace(","," ").split():
        try: vals.append(float(p)); break
        except ValueError: pass
dts=[vals[i+1]-vals[i] for i in range(len(vals)-1) if vals[i+1]>vals[i]]
med=statistics.median(dts) if dts else 0
span=vals[-1]-vals[0]
span_s=span/1e6 if med>1000 else (span/1e3 if med>1 else span)
print(f"frames={len(vals)} med_dt={med:.1f} fps={(len(vals)-1)/span_s:.2f}")
PY
}

echo "=== mem ==="
vcgencmd get_mem arm; vcgencmd get_mem gpu; nproc; cat /proc/cpuinfo | grep -E 'model name|Revision|Hardware' | head -5

echo "=== 720p framerate 20 ==="
rm -f /tmp/fr20.h264 /tmp/fr20.pts
timeout 8 rpicam-vid -n -t 5000 --width 1280 --height 720 --framerate 20 --intra 20 --codec h264 --inline --flush --bitrate 2500000 --denoise cdn_off --buffer-count 2 --save-pts /tmp/fr20.pts -o /tmp/fr20.h264 >/tmp/fr20.log 2>&1 || true
pts_fps /tmp/fr20.pts

echo "=== CPU sample during 720p30 ==="
rm -f /tmp/cpu30.h264 /tmp/cpu30.pts
rpicam-vid -n -t 0 --width 1280 --height 720 --framerate 30 --intra 30 --codec h264 --inline --flush --bitrate 2500000 --denoise cdn_off --buffer-count 2 --save-pts /tmp/cpu30.pts -o /tmp/cpu30.h264 >/tmp/cpu30.log 2>&1 &
RP=$!
sleep 1
for i in 1 2 3 4 5; do
  # busybox-friendly: top batch
  top -b -n 1 | head -12 || true
  sleep 1
done
kill -INT "$RP" 2>/dev/null || true
wait "$RP" 2>/dev/null || true
# pts from whatever was written
if [[ -s /tmp/cpu30.pts ]]; then pts_fps /tmp/cpu30.pts; fi

echo CPU_DIG_DONE
