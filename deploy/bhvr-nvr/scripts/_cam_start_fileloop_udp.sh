#!/bin/bash
# run ON cam1
set -euxo pipefail
pkill -9 -f 'bin/ffmpeg' 2>/dev/null || true
pkill -9 rpicam-vid 2>/dev/null || true
sleep 1
test -x "$HOME/bin/ffmpeg"
test -s /tmp/t.h264
nohup "$HOME/bin/ffmpeg" -hide_banner -loglevel info \
  -re -stream_loop -1 -fflags +genpts -f h264 -i /tmp/t.h264 \
  -c copy -f mpegts "udp://192.168.7.1:15550?pkt_size=1316" \
  >/tmp/ff_udp.log 2>&1 &
echo "started_pid=$!"
sleep 2
pgrep -af ffmpeg || { echo "ffmpeg died"; cat /tmp/ff_udp.log; exit 1; }
tail -15 /tmp/ff_udp.log || true
