#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10)
ssh "${KEY[@]}" admin@192.168.7.27 'bash -s' <<'EOS'
set -uo pipefail
echo "=== libs possibly armv7 ==="
for s in \
  /lib/arm-linux-gnueabihf/liblapack.so.3 \
  /lib/arm-linux-gnueabihf/libgfortran.so.5 \
  /lib/arm-linux-gnueabihf/libopencv_core.so.410 \
  /lib/arm-linux-gnueabihf/librpicam_app.so.1.13.0
do
  if [[ -e "$s" ]]; then
    echo "-- $s"
    readelf -A "$s" 2>/dev/null | grep -E 'Tag_CPU_arch|Tag_CPU_name' || true
    file "$s"
  else
    echo "MISSING $s"
  fi
done
echo "=== rpicam under gdb catch SIGILL ==="
# quick: run and capture dmesg? just strace last syscall
timeout 5 strace -f -e none -e signal=SIGILL rpicam-vid -n -t 2000 --width 640 --height 480 --framerate 15 --codec h264 --inline -o /dev/null 2>&1 | tail -30 || true
EOS
