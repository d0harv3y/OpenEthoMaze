#!/bin/bash
# Smoke: science MPEG-TS SSH pipe produces bytes. Run ON NVR.
set -eu
API=http://127.0.0.1:8080
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
IP=$(curl -sS "$API/api/cams" | python3 -c '
import json,sys
cams=json.load(sys.stdin)["cameras"]
for c in cams:
    if c.get("id")=="bhvr-cam1" and c.get("online"):
        print(c["ip"]); break
else:
    for c in cams:
        if c.get("online") and not str(c.get("ip","")).startswith("192.168.7."):
            print(c["ip"]); break
')
echo "CAM_IP=$IP"
cd "$HOME/bhvr-kiosk"
.venv/bin/python - <<PY
from app.preview import cam_science_ssh_mpegts_remote
print(cam_science_ssh_mpegts_remote(
    width=640, height=480, soft_fps=10, bitrate_bps=800_000, intra=10,
    sensor_mode="640:480", buffer_count=3,
    pts_remote="/home/admin/bhvr-current/timestamps.pts",
    workdir="/home/admin/bhvr-current",
))
PY
REMOTE=$(cd "$HOME/bhvr-kiosk" && .venv/bin/python -c '
from app.preview import cam_science_ssh_mpegts_remote
print(cam_science_ssh_mpegts_remote(
    width=640, height=480, soft_fps=10, bitrate_bps=800_000, intra=10,
    sensor_mode="640:480", buffer_count=3,
    pts_remote="/home/admin/bhvr-current/timestamps.pts",
    workdir="/home/admin/bhvr-current",
))
')
echo "=== 8s pull ==="
timeout 8 ssh "${KEY[@]}" "admin@$IP" "$REMOTE" > /tmp/science_ts_probe.ts 2>/tmp/science_ts_probe.err || true
ls -la /tmp/science_ts_probe.ts /tmp/science_ts_probe.err
echo "=== err ==="
cat /tmp/science_ts_probe.err | tail -40
echo "=== ts head ==="
xxd /tmp/science_ts_probe.ts | head -2 || true
wc -c /tmp/science_ts_probe.ts
