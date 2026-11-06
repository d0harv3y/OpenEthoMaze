#!/bin/bash
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15)

curl -sS http://127.0.0.1:8080/api/health; echo
curl -sS http://127.0.0.1:8080/api/cams; echo

# Announce cam
ssh "${KEY[@]}" admin@192.168.7.27 'bhvr-cam-announce 2>/dev/null || python3 ~/bhvr-cam/scripts/announce_mqtt.py || true'
sleep 1
curl -sS http://127.0.0.1:8080/api/cams; echo

# Start WHEP publish via API
curl -sS -m 30 -X POST http://127.0.0.1:8080/api/preview/bhvr-cam1/whep/start | tee /tmp/whep-start.json
echo

# Check MediaMTX path + WHEP OPTIONS/POST readiness
sleep 2
tail -30 /tmp/mediamtx.log || true
curl -sS -m 5 -o /dev/null -w 'webrtc_page=%{http_code}\n' http://127.0.0.1:8889/bhvr-cam1 || true
# WHEP typically wants POST with SDP; OPTIONS may exist
curl -sS -m 5 -o /dev/null -w 'whep_options=%{http_code}\n' -X OPTIONS http://127.0.0.1:8889/bhvr-cam1/whep || true

ssh "${KEY[@]}" admin@192.168.7.27 'pgrep -a rpicam-vid || echo no_rpicam; pgrep -a ffmpeg || echo no_ffmpeg'

# Leave stream running for operator visual check; print stop hint
echo "LITMUS_API_OK — open kiosk http://127.0.0.1:8080 focus bhvr-cam1"
echo "stop: curl -X POST 'http://127.0.0.1:8080/api/preview/stop?cam_id=bhvr-cam1'"
