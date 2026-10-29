#!/bin/bash
set -uo pipefail
echo "=== page transport ==="
curl -s --max-time 3 http://127.0.0.1:8080/ | grep -E 'PREVIEW_TRANSPORT|preview_transport' | head -5
echo "=== start preview curl (20s) ==="
# background: watch procs
(
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 2
    echo "-- t=$((i*2))s --"
    pgrep -af 'ffmpeg|rpicam|live_udp|ssh.*235' || echo '(no cam/ffmpeg)'
  done
) &
WATCH=$!

curl -s --max-time 20 -o /tmp/preview_out.bin -w "http=%{http_code} size=%{size_download} type=%{content_type}\n" \
  "http://127.0.0.1:8080/api/preview/bhvr-cam0?t=$(date +%s)" || echo "curl_exit=$?"

kill $WATCH 2>/dev/null || true
wait $WATCH 2>/dev/null || true

echo "=== out file ==="
ls -la /tmp/preview_out.bin
xxd /tmp/preview_out.bin | head -5
echo "=== preview logs ==="
ls -la /tmp/bhvr-preview* 2>/dev/null
for f in /tmp/bhvr-preview*; do echo "--- $f ---"; tail -50 "$f"; done
echo "=== health after ==="
curl -s --max-time 3 http://127.0.0.1:8080/api/health; echo
