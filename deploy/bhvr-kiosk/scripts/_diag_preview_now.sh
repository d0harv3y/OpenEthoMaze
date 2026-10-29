#!/bin/bash
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74

echo "=== health ==="
curl -s http://127.0.0.1:8080/api/health; echo

echo "=== cam ssh ==="
ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 "admin@${CAM}" \
  'hostname; pgrep -af rpicam||echo no_rpicam; pgrep -af ffmpeg||echo no_ff; df -h ~ | tail -1'

echo "=== stop leftovers ==="
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'pkill -INT rpicam-vid; pkill -9 rpicam-vid; pkill -f "ffmpeg.*mpegts"; true' || true
curl -s -X POST 'http://127.0.0.1:8080/api/preview/stop' >/dev/null || true
sleep 1

echo "=== direct SSH mpegts 6s ==="
# same remote as app, run from NVR
timeout 6 ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'stdbuf -o0 rpicam-vid -n -t 0 --width 640 --height 480 --framerate 10 --codec h264 --inline --intra 10 --flush --bitrate 800000 --denoise cdn_off --buffer-count 2 -o - | ffmpeg -hide_banner -loglevel warning -nostats -fflags nobuffer+genpts+flush_packets -flags low_delay -f h264 -framerate 10 -i pipe:0 -c copy -muxdelay 0 -muxpreload 0 -flush_packets 1 -f mpegts pipe:1' \
  > /tmp/direct_ssh.ts 2>/tmp/direct_ssh.err || true
ls -la /tmp/direct_ssh.ts /tmp/direct_ssh.err
wc -c /tmp/direct_ssh.ts
tail -20 /tmp/direct_ssh.err
ffprobe -v error -show_entries stream=codec_name,width,height -of default=nw=1 /tmp/direct_ssh.ts 2>&1 | head -8

echo "=== API preview 15s ==="
rm -f /tmp/api_prev.ts
timeout 15 curl -sSN -D /tmp/api_prev.hdr -o /tmp/api_prev.ts \
  'http://127.0.0.1:8080/api/preview/bhvr-cam0' || echo curl_exit=$?
head -20 /tmp/api_prev.hdr
ls -la /tmp/api_prev.ts 2>/dev/null || echo NO
tail -30 /tmp/bhvr-preview-bhvr-cam0.log 2>/dev/null || echo no_nvr_log
curl -s -X POST 'http://127.0.0.1:8080/api/preview/stop?cam_id=bhvr-cam0'; echo
