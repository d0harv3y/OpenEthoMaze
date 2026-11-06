#!/bin/bash
set -uo pipefail
pkill -f '_litmus_fanout_x4' 2>/dev/null || true
pkill -f 'nc -l -p 1656' 2>/dev/null || true
pkill -f 'ffmpeg.*127.0.0.1:155' 2>/dev/null || true
sleep 1
echo "clean_ffmpeg=$(pgrep -c ffmpeg || echo 0)"

# Four coupled pipelines like ×4, feed from /dev/zero briefly? Better: real cam0 only first.
# Check whether libx264 ×4 can start:
for n in 0 1 2 3; do
  tcp=$((16560 + n))
  mtx=$((15550 + n))
  rm -f "/tmp/c${n}.h264" "/tmp/c${n}.log"
  nc -l -p "$tcp" | ffmpeg -hide_banner -loglevel info \
    -f h264 -i pipe:0 \
    -map 0:v -c:v copy -f h264 "/tmp/c${n}.h264" \
    -map 0:v -vf scale=480:270,fps=10 -c:v libx264 -preset ultrafast -threads 1 \
    -an -f mpegts "udp://127.0.0.1:${mtx}?pkt_size=1316&overrun_nonfatal=1" \
    >"/tmp/c${n}.log" 2>&1 &
  echo "started n=$n pid=$!"
done
sleep 2
echo "ffmpeg_count=$(pgrep -c ffmpeg || echo 0)"
pgrep -af 'ffmpeg|nc -l' | head -20
for n in 0 1 2 3; do
  echo "=== log $n ==="
  tail -15 "/tmp/c${n}.log" || true
done
