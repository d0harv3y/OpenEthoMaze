#!/bin/bash
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74

ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" bash -s <<'CAM'
set +e
pkill -9 rpicam-vid; pkill -9 ffmpeg; sleep 1
echo "=== rpicam help codec ==="
rpicam-vid --help 2>&1 | grep -iE 'libav|mpegts|codec|inline' | head -40
echo "=== try libav mpegts 8s ==="
timeout 8 rpicam-vid -n -t 0 --width 640 --height 480 --framerate 10 \
  --codec libav --libav-format mpegts --libav-video-codec h264 \
  --bitrate 800000 --inline -o - > /tmp/libav.ts 2>/tmp/libav.err
ls -la /tmp/libav.ts /tmp/libav.err
wc -c /tmp/libav.ts
tail -30 /tmp/libav.err
# if file on cam, scp-less: just report
ffprobe -v error -show_entries stream=codec_name,width,height -show_entries packet=pts_time -of default=nw=1 /tmp/libav.ts 2>&1 | head -15
CAM
