#!/bin/bash
# Compare SSH stdout MPEG-TS vs on-cam file. ON NVR.
set -eu
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
IP=10.248.233.15

echo "=== A: idle remote (preview.py) via SSH stdout ==="
REMOTE=$(cd "$HOME/bhvr-kiosk" && .venv/bin/python -c 'from app.preview import cam_live_ssh_mpegts_remote, preview_settings; print(cam_live_ssh_mpegts_remote(preview_settings({"preview":{"transport":"mpegts","buffer_count":3}})))')
timeout 10 ssh "${KEY[@]}" "admin@$IP" "$REMOTE" > /tmp/idle_ssh.ts 2>/tmp/idle_ssh.err || true
wc -c /tmp/idle_ssh.ts
tail -5 /tmp/idle_ssh.err

echo "=== B: bash -lc wrapper + pipe:1 ==="
timeout 10 ssh "${KEY[@]}" "admin@$IP" bash -lc '
pkill -INT rpicam-vid 2>/dev/null || true
pkill -x ffmpeg 2>/dev/null || true
sleep 0.3
FF=$HOME/bin/ffmpeg
stdbuf -o0 rpicam-vid -n -t 0 --mode 640:480:10:P --width 640 --height 480 \
  --framerate 10 --codec h264 --inline --intra 10 --flush --bitrate 800000 \
  --denoise cdn_off --buffer-count 3 -o - \
| $FF -hide_banner -loglevel warning -nostats \
  -use_wallclock_as_timestamps 1 -fflags +genpts+nobuffer+flush_packets \
  -flags low_delay -avioflags direct -f h264 -i pipe:0 -c copy \
  -muxdelay 0 -muxpreload 0 -flush_packets 1 -f mpegts pipe:1
' > /tmp/bashlc_ssh.ts 2>/tmp/bashlc_ssh.err || true
wc -c /tmp/bashlc_ssh.ts
tail -8 /tmp/bashlc_ssh.err

echo "=== C: same as B but stdbuf -o0 on ffmpeg ==="
timeout 10 ssh "${KEY[@]}" "admin@$IP" bash -lc '
pkill -INT rpicam-vid 2>/dev/null || true
pkill -x ffmpeg 2>/dev/null || true
sleep 0.3
FF=$HOME/bin/ffmpeg
stdbuf -o0 rpicam-vid -n -t 0 --mode 640:480:10:P --width 640 --height 480 \
  --framerate 10 --codec h264 --inline --intra 10 --flush --bitrate 800000 \
  --denoise cdn_off --buffer-count 3 -o - \
| stdbuf -o0 $FF -hide_banner -loglevel warning -nostats \
  -use_wallclock_as_timestamps 1 -fflags +genpts+nobuffer+flush_packets \
  -flags low_delay -avioflags direct -f h264 -i pipe:0 -c copy \
  -muxdelay 0 -muxpreload 0 -flush_packets 1 -f mpegts pipe:1
' > /tmp/stdbuf_ssh.ts 2>/tmp/stdbuf_ssh.err || true
wc -c /tmp/stdbuf_ssh.ts
