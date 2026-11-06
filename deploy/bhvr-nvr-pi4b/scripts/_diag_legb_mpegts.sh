#!/bin/bash
set -eu
CAM=bhvr-cam2
IP=10.248.229.141
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10)

echo "=== health ==="
curl -sS http://127.0.0.1:8080/api/health; echo
echo "=== preview knobs ==="
grep -E 'transport:|nvr_host:|buffer_count:|whep_ingest:' "$HOME/bhvr-kiosk/config.yaml" || true

echo "=== stop then GET mpegts 8s ==="
curl -sS -X POST http://127.0.0.1:8080/api/preview/stop >/dev/null || true
sleep 1
curl -sS -o /tmp/legb.ts -w "HTTP %{http_code} bytes=%{size_download} ctype=%{content_type}\n" \
  --max-time 8 "http://127.0.0.1:8080/api/preview/${CAM}?t=diag" || true
ls -la /tmp/legb.ts || true
xxd /tmp/legb.ts 2>/dev/null | head -2 || od -An -tx1 /tmp/legb.ts | head -2

echo "=== cam processes during/after ==="
ssh "${KEY[@]}" "admin@$IP" 'pgrep -a rpicam-vid; pgrep -a ffmpeg; ls -la /tmp/*rpicam* /tmp/*preview* 2>/dev/null | head' 2>&1 || true

echo "=== NVR preview logs ==="
ls -la /tmp/bhvr-preview-* 2>/dev/null | tail -15 || true
for f in /tmp/bhvr-preview-${CAM}* /tmp/bhvr-preview-*${CAM}*; do
  if [ -f "$f" ]; then
    echo "==== $f"
    tail -50 "$f" || true
  fi
done

echo "=== kiosk log (preview/mpegts) ==="
grep -E 'preview|mpegts|cam2|Error|Traceback|FAIL' /tmp/kiosk-web.log | tail -40 || tail -40 /tmp/kiosk-web.log

echo "=== direct ssh mpegts smoke on cam (5s) ==="
ssh "${KEY[@]}" "admin@$IP" 'bash -s' <<'EOC'
set -e
pkill -INT rpicam-vid 2>/dev/null || true
pkill -f 'ffmpeg.*mpegts' 2>/dev/null || true
sleep 0.3
timeout 6 bash -c '
  rpicam-vid -n -t 0 --mode 640:480:10:P --width 640 --height 480 --framerate 10 \
    --codec h264 --inline --intra 10 --flush --bitrate 800000 --denoise cdn_off \
    --buffer-count 2 -o - \
  | ffmpeg -hide_banner -loglevel warning -f h264 -i pipe:0 -c copy -f mpegts - 2>/tmp/ff_legb_cam.err \
  | head -c 100000 > /tmp/legb_cam.ts
' || true
ls -la /tmp/legb_cam.ts /tmp/ff_legb_cam.err 2>/dev/null || true
tail -20 /tmp/ff_legb_cam.err 2>/dev/null || true
EOC
scp "${KEY[@]}" "admin@$IP:/tmp/legb_cam.ts" /tmp/legb_cam_from_cam.ts 2>/dev/null || true
ls -la /tmp/legb_cam_from_cam.ts 2>/dev/null || true
