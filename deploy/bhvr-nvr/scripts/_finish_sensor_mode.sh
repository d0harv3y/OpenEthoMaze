#!/bin/bash
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
.venv/bin/python <<'PY'
from app.preview import (
    cam_sensor_mode,
    rpicam_mode_flag,
    cam_live_udp_remote,
    preview_settings,
    normalize_sensor_mode,
)
assert normalize_sensor_mode("1296x972") == "1296:972"
assert rpicam_mode_flag("auto") == ""
assert "--mode 1296:972:10:P" in rpicam_mode_flag("1296:972")
cfg = {
    "preview": {"sensor_mode": "auto", "udp_port": 15550},
    "cam_sensor_mode": {"bhvr-cam1": "1296:972"},
}
assert cam_sensor_mode(cfg, "bhvr-cam1") == "1296:972"
s = preview_settings(cfg, cam_id="bhvr-cam1")
assert "1296:972" in cam_live_udp_remote(s, "192.168.7.1", 15550)
print("unit_ok")
PY

pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >/tmp/kiosk-uvicorn.log 2>&1 &
sleep 2
curl -sS http://127.0.0.1:8080/api/health
echo
curl -sS -X PUT http://127.0.0.1:8080/api/cams/bhvr-cam1/sensor-mode \
  -H 'Content-Type: application/json' \
  -d '{"sensor_mode":"1296:972"}'
echo
curl -sS http://127.0.0.1:8080/api/cams/bhvr-cam1/sensor-mode
echo
tail -15 /tmp/kiosk-uvicorn.log || true
