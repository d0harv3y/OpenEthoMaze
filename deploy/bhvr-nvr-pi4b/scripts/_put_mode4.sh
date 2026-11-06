#!/bin/bash
set -euxo pipefail
curl -sS -X PUT "http://127.0.0.1:8080/api/cams/bhvr-cam1/sensor-mode" \
  -H "Content-Type: application/json" \
  --data-binary '{"sensor_mode":"1296:972"}'
echo
curl -sS "http://127.0.0.1:8080/api/cams/bhvr-cam1/sensor-mode"
echo
grep -A5 cam_sensor_mode "$HOME/bhvr-kiosk/config.yaml" || true
