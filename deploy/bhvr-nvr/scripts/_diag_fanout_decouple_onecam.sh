#!/bin/bash
# Smoke: one-cam Stage A/B decoupled → MediaMTX RTSP
set -euo pipefail
CAM=bhvr-cam0
TCP=16560
RAW=15670
MTX=15550
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
IP=$(python3 - <<'PY'
import json, urllib.request
h = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=8))
for c in h.get("cameras") or []:
    if c.get("id") == "bhvr-cam0":
        print(c["ip"]); break
PY
)
echo "IP=$IP"
pkill -f "nc -l -p 16560" 2>/dev/null || true
pkill -f "udp://0.0.0.0:15670" 2>/dev/null || true
pkill -f "fanout_bhvr-cam0" 2>/dev/null || true
ssh "${KEY[@]}" "admin@$IP" 'pkill -INT rpicam-vid 2>/dev/null || true; pkill -x nc 2>/dev/null || true' || true
sleep 1
rm -f /tmp/fanout_bhvr-cam0_science.h264 /tmp/d_ingest.log /tmp/d_scale.log

nc -l -p "$TCP" | ffmpeg -hide_banner -loglevel info -nostats \
  -fflags +genpts+nobuffer -use_wallclock_as_timestamps 1 \
  -f h264 -i pipe:0 \
  -map 0:v -c:v copy -f h264 /tmp/fanout_bhvr-cam0_science.h264 \
  -map 0:v -c:v copy -muxdelay 0 -mpegts_flags +resend_headers \
    -f mpegts "udp://127.0.0.1:${RAW}?pkt_size=1316&overrun_nonfatal=1" \
  >/tmp/d_ingest.log 2>&1 &
INGEST=$!

ffmpeg -hide_banner -loglevel info -nostats \
  -fflags +genpts+igndts+discardcorrupt \
  -analyzeduration 2000000 -probesize 2000000 \
  -f mpegts -i "udp://0.0.0.0:${RAW}?reuse=1&fifo_size=1000000&overrun_nonfatal=1" \
  -vf "scale=480:270,fps=10" \
  -c:v libx264 -preset ultrafast -tune zerolatency -g 10 -threads 1 \
  -an -f mpegts "udp://127.0.0.1:${MTX}?pkt_size=1316&overrun_nonfatal=1" \
  >/tmp/d_scale.log 2>&1 &
SCALE=$!

ssh "${KEY[@]}" "admin@$IP" "nohup bash -c 'rpicam-vid -n -t 0 --mode 1920:1080:10:P --width 1920 --height 1080 --framerate 30 --codec h264 --inline --intra 30 --flush --bitrate 4000000 --denoise cdn_off --buffer-count 6 -o - | nc -N 192.168.7.1 ${TCP}' >/tmp/fanout_pub.log 2>&1 &"

for i in $(seq 1 20); do
  if out=$(ffprobe -rtsp_transport tcp -v error -select_streams v:0 \
      -show_entries stream=codec_name,width,height,r_frame_rate -of csv=p=0 \
      "rtsp://127.0.0.1:8554/${CAM}" 2>/dev/null); then
    echo "READY $out"
    break
  fi
  echo "wait_$i ffmpeg=$(pgrep -c ffmpeg || echo 0)"
  sleep 1
done
echo "=== ingest tail ==="; tail -15 /tmp/d_ingest.log
echo "=== scale tail ==="; tail -20 /tmp/d_scale.log
echo "=== science ==="; wc -c /tmp/fanout_bhvr-cam0_science.h264 || true
ssh "${KEY[@]}" "admin@$IP" 'pkill -INT rpicam-vid 2>/dev/null; pkill -x nc 2>/dev/null' || true
kill "$INGEST" "$SCALE" 2>/dev/null || true
pkill -f "nc -l -p 16560" 2>/dev/null || true
echo DONE
