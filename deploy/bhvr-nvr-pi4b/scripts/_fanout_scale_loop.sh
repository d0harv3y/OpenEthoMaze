#!/bin/bash
# Usage: _fanout_scale_loop.sh <cam_id> <raw_udp> <mtx_udp> <w> <h> <fps>
set -uo pipefail
CAM=$1
RAW=$2
MTX=$3
W=$4
H=$5
FPS=$6
LOG=/tmp/fanout_${CAM}_scale.log
: >"$LOG"
while true; do
  echo "$(date -Is) scale restart $CAM raw=$RAW mtx=$MTX" >>"$LOG"
  ffmpeg -hide_banner -loglevel warning -nostats \
    -fflags +nobuffer+discardcorrupt -flags low_delay \
    -analyzeduration 2000000 -probesize 2000000 \
    -f mpegts -i "udp://0.0.0.0:${RAW}?reuse=1&fifo_size=1000000&overrun_nonfatal=1" \
    -vf "scale=${W}:${H},fps=${FPS}" \
    -c:v libx264 -preset ultrafast -tune zerolatency -g "$FPS" -threads 1 \
    -an -f mpegts "udp://127.0.0.1:${MTX}?pkt_size=1316&overrun_nonfatal=1" \
    >>"$LOG" 2>&1 || true
  sleep 1
done
