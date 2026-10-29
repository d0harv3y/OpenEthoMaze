#!/bin/bash
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
CAM_ID=bhvr-cam0

ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'pkill -INT rpicam-vid; pkill -f live_udp; pkill -f "ffmpeg.*udp"; true' || true
curl -s -X POST "http://127.0.0.1:8080/api/preview/stop?cam_id=${CAM_ID}" >/dev/null || true
sleep 1

rm -f /tmp/preview_udp.ts
echo "=== GET /api/preview/${CAM_ID} (30s, -N) ==="
# Wait for MQTT roster if kiosk just restarted
for i in 1 2 3 4 5 6; do
  n=$(curl -s http://127.0.0.1:8080/api/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('roster_size',0))")
  echo "roster_size=$n"
  [ "$n" -ge 1 ] && break
  sleep 2
done
timeout 30 curl -sSN -o /tmp/preview_udp.ts -w "http=%{http_code} bytes=%{size_download}\n" \
  "http://127.0.0.1:8080/api/preview/${CAM_ID}" || echo "curl_exit=$?"
ls -la /tmp/preview_udp.ts
file /tmp/preview_udp.ts
echo "=== ffprobe ==="
ffprobe -v error -show_entries stream=codec_name,width,height -of default=nw=1 /tmp/preview_udp.ts 2>&1 | head -15
echo "=== nvr ffmpeg log ==="
tail -40 /tmp/bhvr-preview-${CAM_ID}.log 2>/dev/null || echo "(none)"
echo "=== cam ssh log ==="
tail -30 /tmp/bhvr-preview-${CAM_ID}-cam.log 2>/dev/null || echo "(none)"
echo "=== health ==="
curl -s http://127.0.0.1:8080/api/health
echo
curl -s -X POST "http://127.0.0.1:8080/api/preview/stop?cam_id=${CAM_ID}"
echo
