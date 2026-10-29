#!/bin/bash
# Run encode on cam to a local file (bypass SSH stdout quirks). ON NVR.
set -eu
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
IP=10.248.233.15
ssh "${KEY[@]}" "admin@$IP" 'bash -s' <<'EOS'
set -eux
pkill -INT rpicam-vid 2>/dev/null || true
pkill -x ffmpeg 2>/dev/null || true
sleep 0.5
FFMPEG="$HOME/bin/ffmpeg"
test -x "$FFMPEG"
rm -f /tmp/t.ts /tmp/t.err /tmp/t.pts
timeout 6 bash -c '
  stdbuf -o0 rpicam-vid -n -t 0 --mode 640:480:10:P --width 640 --height 480 \
    --framerate 10 --codec h264 --inline --intra 10 --flush --bitrate 800000 \
    --denoise cdn_off --buffer-count 3 --save-pts /tmp/t.pts -o - \
  | '"$FFMPEG"' -hide_banner -loglevel info -nostats \
    -use_wallclock_as_timestamps 1 -fflags +genpts+nobuffer+flush_packets \
    -flags low_delay -avioflags direct -f h264 -i pipe:0 -c copy \
    -muxdelay 0 -muxpreload 0 -flush_packets 1 -f mpegts /tmp/t.ts
' > /tmp/t.err 2>&1 || true
ls -la /tmp/t.ts /tmp/t.pts /tmp/t.err
wc -c /tmp/t.ts /tmp/t.pts
tail -30 /tmp/t.err
pgrep -a rpicam || true
pgrep -a ffmpeg || true
EOS
scp "${KEY[@]}" "admin@$IP:/tmp/t.ts" /tmp/t_from_cam.ts 2>/dev/null || true
ls -la /tmp/t_from_cam.ts 2>/dev/null || true
