#!/bin/bash
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20)
CAM=admin@192.168.7.27

# Clear any leftover encoders; let kiosk start publish.
ssh "${KEY[@]}" "$CAM" 'killall -9 rpicam-vid 2>/dev/null || true; killall -9 ffmpeg 2>/dev/null || true; true'

curl -sS -m 3 http://127.0.0.1:8080/api/health || true
echo
curl -sS -m 3 http://127.0.0.1:8080/docs 2>/dev/null | head -c 200 || true
echo
# Discover roster-ish endpoints
python3 - <<'PY'
import urllib.request, json
base="http://127.0.0.1:8080"
for path in ["/api/health","/api/cams","/api/cameras","/api/roster","/api/status","/health"]:
    try:
        with urllib.request.urlopen(base+path, timeout=3) as r:
            body=r.read(500)
            print(path, r.status, body[:200])
    except Exception as e:
        print(path, type(e).__name__, e)
PY

# Force announce then preview pull
ssh "${KEY[@]}" "$CAM" 'command -v bhvr-cam-announce >/dev/null && bhvr-cam-announce || python3 ~/bhvr-cam/scripts/announce_mqtt.py || true'
sleep 2

python3 - <<'PY'
import urllib.request, json
base="http://127.0.0.1:8080"
for path in ["/api/cams","/api/cameras","/api/roster","/api/status"]:
    try:
        with urllib.request.urlopen(base+path, timeout=3) as r:
            print("AFTER", path, r.read(800).decode())
    except Exception as e:
        print("AFTER", path, e)
PY

# Pull preview bytes (kiosk should SSH-start live_udp_mpegts then remux)
rm -f /tmp/udp-prev.bin
timeout 15 curl -sS -o /tmp/udp-prev.bin -w 'bytes=%{size_download} http=%{http_code}\n' \
  http://127.0.0.1:8080/api/preview/bhvr-cam1 || true
wc -c /tmp/udp-prev.bin || true
xxd /tmp/udp-prev.bin | head -3 || true

echo "=== preview logs ==="
ls -la /tmp/bhvr-preview* 2>/dev/null || true
tail -40 /tmp/bhvr-preview-bhvr-cam1.log 2>/dev/null || true
tail -40 /tmp/bhvr-preview-bhvr-cam1-cam.log 2>/dev/null || true
tail -40 /tmp/kiosk-uvicorn.log 2>/dev/null || true

echo "=== cam procs ==="
ssh "${KEY[@]}" "$CAM" 'pgrep -a rpicam-vid || echo no_rpicam; pgrep -a ffmpeg || echo no_ffmpeg; tail -20 /tmp/live_udp.log 2>/dev/null || true'
