#!/bin/bash
# run ON cam1 — live rpicam -> ffmpeg -> UDP MPEG-TS
set -euxo pipefail
pkill -9 -f 'bin/ffmpeg' 2>/dev/null || true
pkill -9 rpicam-vid 2>/dev/null || true
sleep 1
test -x "$HOME/bin/ffmpeg"

# Prefer stdin pipe; force mpegts mux before network open delays.
# -probesize/-analyzeduration keep demux from stalling on annex-B.
nohup bash -c '
rpicam-vid -n -t 0 --width 1280 --height 720 --framerate 30 \
  --codec h264 --inline --bitrate 2500000 -o - \
| ~/bin/ffmpeg -hide_banner -loglevel info \
  -fflags +genpts+nobuffer -flags low_delay \
  -probesize 32 -analyzeduration 0 \
  -f h264 -i pipe:0 \
  -c copy -f mpegts "udp://192.168.7.1:15550?pkt_size=1316&fifo_size=1000000&overrun_nonfatal=1"
' >/tmp/ff_live.log 2>&1 &
echo "started_pid=$!"
sleep 4
pgrep -af 'rpicam-vid|ffmpeg' || { echo "procs died"; cat /tmp/ff_live.log; exit 1; }
tail -40 /tmp/ff_live.log || true
