#!/bin/bash
# Run ON cam1 — remeasure 720p30 with avahi stopped (needs passwordless sudo or already stopped)
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

echo "=== before ==="
pgrep -a avahi || echo no_avahi
top -b -n 1 | head -8

if sudo -n true 2>/dev/null; then
  sudo -n systemctl stop avahi-daemon.service avahi-daemon.socket 2>/dev/null || sudo -n killall -9 avahi-daemon || true
else
  # try user-kill (won't work for root avahi) — report
  echo "NOTE: no passwordless sudo; attempting killall (may fail)"
  sudo killall -9 avahi-daemon 2>/dev/null || killall -9 avahi-daemon 2>/dev/null || true
fi
sleep 1
pgrep -a avahi || echo avahi_stopped

rm -f /tmp/nav.h264 /tmp/nav.pts
timeout 8 rpicam-vid -n -t 5000 --width 1280 --height 720 --framerate 30 --intra 30 --codec h264 --inline --flush --bitrate 2500000 --denoise cdn_off --buffer-count 2 --save-pts /tmp/nav.pts -o /tmp/nav.h264 >/tmp/nav.log 2>&1 || true
pts_fps /tmp/nav.pts
top -b -n 1 | head -10

# restart avahi if we stopped via systemd
if sudo -n true 2>/dev/null; then
  sudo -n systemctl start avahi-daemon.service 2>/dev/null || true
fi
echo NOAVAHI_DONE
