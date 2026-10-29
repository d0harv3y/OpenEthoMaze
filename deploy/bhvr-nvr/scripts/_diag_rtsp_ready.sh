#!/bin/bash
set -uo pipefail
echo "ffmpeg=$(pgrep -c ffmpeg || echo 0) load=$(cut -d' ' -f1-3 /proc/loadavg)"
for c in bhvr-cam0 bhvr-cam1 bhvr-cam2 bhvr-cam3; do
  out=$(timeout 5 ffprobe -rtsp_transport tcp -v error -select_streams v:0 \
    -show_entries stream=codec_name,width,height,r_frame_rate -of csv=p=0 \
    "rtsp://127.0.0.1:8554/${c}" 2>/dev/null || true)
  echo "$c ${out:-FAIL}"
  wc -c "/tmp/fanout_${c}_science.h264" 2>/dev/null || true
  tail -3 "/tmp/fanout_${c}_scale.log" 2>/dev/null || true
done
ss -ulnp | grep -E '1567|1555' | head -20
