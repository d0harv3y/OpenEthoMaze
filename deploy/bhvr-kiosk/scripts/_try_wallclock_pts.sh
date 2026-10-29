#!/bin/bash
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74

ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" 'pkill -9 rpicam-vid; pkill -9 ffmpeg; true' || true
sleep 1

echo "=== wallclock genpts 10s ==="
timeout 10 ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'stdbuf -o0 rpicam-vid -n -t 0 --width 640 --height 480 --framerate 10 --codec h264 --inline --intra 10 --flush --bitrate 800000 --denoise cdn_off --buffer-count 2 -o - | ffmpeg -hide_banner -loglevel warning -nostats -use_wallclock_as_timestamps 1 -fflags +genpts+nobuffer+flush_packets -flags low_delay -avioflags direct -f h264 -i pipe:0 -c copy -muxdelay 0 -muxpreload 0 -flush_packets 1 -f mpegts pipe:1' \
  > /tmp/wc.ts 2>/tmp/wc.err || true
ls -la /tmp/wc.ts
ffprobe -v error -show_entries packet=pts_time -of csv=p=0 /tmp/wc.ts 2>/dev/null | head -8
ffprobe -v warning -i /tmp/wc.ts 2>&1 | grep -E 'unset|Stream|Duration' | head -10
tail -5 /tmp/wc.err
