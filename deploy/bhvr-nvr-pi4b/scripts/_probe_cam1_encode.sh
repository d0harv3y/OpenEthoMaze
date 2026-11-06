#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10)
CAM=admin@192.168.7.27

ssh "${KEY[@]}" "$CAM" 'bash -s' <<'EOS'
set -uo pipefail
echo "=== dpkg broken ==="
dpkg -l ffmpeg rpicam-apps rpicam-apps-core rpicam-apps-encoder 2>/dev/null | tail -10
echo "=== rpicam alone 3s ==="
timeout 4 rpicam-vid -n -t 3000 --width 640 --height 480 --framerate 15 --codec h264 --inline -o /tmp/t.h264 2>/tmp/rpicam_t.err
echo "rpicam_exit=$?"
ls -la /tmp/t.h264 2>/dev/null || echo no_h264
wc -c /tmp/t.h264 2>/dev/null || true
tail -20 /tmp/rpicam_t.err || true
echo "=== which ffmpeg in live script ==="
FFMPEG_BIN=""
for c in "${HOME}/bin/ffmpeg" /usr/local/bin/ffmpeg ffmpeg; do
  if [[ "$c" == ffmpeg ]]; then
    command -v ffmpeg >/dev/null && FFMPEG_BIN=$(command -v ffmpeg) && break
  elif [[ -x "$c" ]]; then
    FFMPEG_BIN="$c"
    break
  fi
done
echo "FFMPEG_BIN=$FFMPEG_BIN"
"$FFMPEG_BIN" -version 2>&1 | head -1
echo "=== live script 8s ==="
killall -9 rpicam-vid 2>/dev/null || true
killall -9 ffmpeg 2>/dev/null || true
timeout 8 ~/bhvr-cam/scripts/live_udp_mpegts.sh 192.168.7.1 15550 1280 720 15 2500 2 1920:1080 >/tmp/live_try.log 2>&1 &
LP=$!
sleep 5
pgrep -a rpicam-vid || echo no_rpicam
pgrep -a ffmpeg || echo no_ffmpeg
wait "$LP" 2>/dev/null || true
echo "--- live_try.log ---"
cat /tmp/live_try.log
EOS

echo '=== nvr full preview logs ==='
wc -c /tmp/bhvr-preview-bhvr-cam1-cam.log /tmp/bhvr-preview-bhvr-cam1.log 2>/dev/null || true
tail -80 /tmp/bhvr-preview-bhvr-cam1-cam.log 2>/dev/null || true
echo '---'
tail -40 /tmp/bhvr-preview-bhvr-cam1.log 2>/dev/null || true
