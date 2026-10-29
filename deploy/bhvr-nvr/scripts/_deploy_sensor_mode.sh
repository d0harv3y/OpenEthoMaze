#!/bin/bash
set -euxo pipefail
SRC=/tmp/bhvr-sensor-deploy
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20)
KIOSK="$HOME/bhvr-kiosk"

cp -f "$SRC/preview.py" "$KIOSK/app/preview.py"
cp -f "$SRC/main.py" "$KIOSK/app/main.py"
cp -f "$SRC/index.html" "$KIOSK/app/templates/index.html"
cp -f "$SRC/config.example.yaml" "$KIOSK/config.example.yaml"
cp -f "$SRC/test_preview_settings.py" "$KIOSK/tests/test_preview_settings.py" 2>/dev/null || true

# Push live_udp script to cam1
scp "${KEY[@]}" "$SRC/live_udp_mpegts.sh" admin@192.168.7.27:/tmp/live_udp_mpegts.sh
ssh "${KEY[@]}" admin@192.168.7.27 'mkdir -p ~/bhvr-cam/scripts; sed "s/\r$//" /tmp/live_udp_mpegts.sh > ~/bhvr-cam/scripts/live_udp_mpegts.sh; chmod +x ~/bhvr-cam/scripts/live_udp_mpegts.sh'

cd "$KIOSK"
.venv/bin/python -m pytest tests/test_preview_settings.py -q

pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >/tmp/kiosk-uvicorn.log 2>&1 &
sleep 2
curl -sS http://127.0.0.1:8080/api/health; echo
curl -sS http://127.0.0.1:8080/api/cams | head -c 600; echo
curl -sS -X PUT http://127.0.0.1:8080/api/cams/bhvr-cam1/sensor-mode \
  -H 'Content-Type: application/json' \
  -d '{"sensor_mode":"1296:972"}'; echo
curl -sS http://127.0.0.1:8080/api/cams/bhvr-cam1/sensor-mode; echo
echo DEPLOY_SENSOR_OK
