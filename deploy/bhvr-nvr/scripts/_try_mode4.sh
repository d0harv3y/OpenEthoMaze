#!/bin/bash
# NVR → cam1: OV5647 "mode 4" style 1296x972 binned vs default 1080p path
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20)

curl -sS -X POST 'http://127.0.0.1:8080/api/preview/stop' || true

ssh "${KEY[@]}" admin@192.168.7.27 'bash -s' <<'EOC'
set -euxo pipefail
killall -9 rpicam-vid 2>/dev/null || true
killall -9 ffmpeg 2>/dev/null || true

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
if len(vals)<2:
    print("fps=NA"); raise SystemExit
dts=[vals[i+1]-vals[i] for i in range(len(vals)-1) if vals[i+1]>vals[i]]
med=statistics.median(dts)
span=vals[-1]-vals[0]
span_s=span/1e6 if med>1000 else (span/1e3 if med>1 else span)
print(f"frames={len(vals)} med_dt={med:.1f} fps={(len(vals)-1)/span_s:.2f}")
PY
}

echo "=== libcamera modes on this cam ==="
rpicam-vid --list-cameras 2>&1 | head -20

echo "=== default (auto → usually 1920x1080) 720p30 5s ==="
rm -f /tmp/m_def.pts /tmp/m_def.h264 /tmp/m_def.log
timeout 8 rpicam-vid -n -t 5000 --width 1280 --height 720 --framerate 30 --intra 30 \
  --codec h264 --inline --flush --bitrate 2500000 --denoise cdn_off --buffer-count 2 \
  --save-pts /tmp/m_def.pts -o /tmp/m_def.h264 >/tmp/m_def.log 2>&1 || true
pts_fps /tmp/m_def.pts
grep -E 'Mode selection|Selected sensor' /tmp/m_def.log | head -6

echo "=== mode 4-ish: --mode 1296:972:10:P → 1280x720@30 5s ==="
rm -f /tmp/m4.pts /tmp/m4.h264 /tmp/m4.log
timeout 8 rpicam-vid -n -t 5000 --mode 1296:972:10:P --width 1280 --height 720 --framerate 30 --intra 30 \
  --codec h264 --inline --flush --bitrate 2500000 --denoise cdn_off --buffer-count 2 \
  --save-pts /tmp/m4.pts -o /tmp/m4.h264 >/tmp/m4.log 2>&1 || true
pts_fps /tmp/m4.pts
grep -E 'Mode selection|Selected sensor' /tmp/m4.log | head -6

echo "=== mode 4 native 1296x972@30 (no scale to 720) 5s ==="
rm -f /tmp/m4n.pts /tmp/m4n.h264 /tmp/m4n.log
timeout 8 rpicam-vid -n -t 5000 --mode 1296:972:10:P --width 1296 --height 972 --framerate 30 --intra 30 \
  --codec h264 --inline --flush --bitrate 2500000 --denoise cdn_off --buffer-count 2 \
  --save-pts /tmp/m4n.pts -o /tmp/m4n.h264 >/tmp/m4n.log 2>&1 || true
pts_fps /tmp/m4n.pts
grep -E 'Mode selection|Selected sensor' /tmp/m4n.log | head -6

echo "=== mode 4 native @42 (sensor max-ish) 5s ==="
rm -f /tmp/m4f.pts /tmp/m4f.h264 /tmp/m4f.log
timeout 8 rpicam-vid -n -t 5000 --mode 1296:972:10:P --width 1296 --height 972 --framerate 42 --intra 42 \
  --codec h264 --inline --flush --bitrate 2500000 --denoise cdn_off --buffer-count 2 \
  --save-pts /tmp/m4f.pts -o /tmp/m4f.h264 >/tmp/m4f.log 2>&1 || true
pts_fps /tmp/m4f.pts
grep -E 'Mode selection|Selected sensor' /tmp/m4f.log | head -6
EOC
