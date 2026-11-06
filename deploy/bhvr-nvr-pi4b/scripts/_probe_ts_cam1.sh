#!/bin/bash
set -eu
sleep 3
curl -sS http://127.0.0.1:8080/api/cams | python3 -m json.tool | head -40
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
IP=10.248.233.15
REMOTE=$(cd "$HOME/bhvr-kiosk" && .venv/bin/python - <<'PY'
from app.preview import cam_science_ssh_mpegts_remote
print(cam_science_ssh_mpegts_remote(
    width=640, height=480, soft_fps=10, bitrate_bps=800_000, intra=10,
    sensor_mode="640:480", buffer_count=3,
    pts_remote="/home/admin/bhvr-current/timestamps.pts",
    workdir="/home/admin/bhvr-current",
))
PY
)
echo "REMOTE_HAS_pkill_x=$(echo "$REMOTE" | grep -c 'pkill -x ffmpeg' || true)"
timeout 8 ssh "${KEY[@]}" "admin@$IP" "$REMOTE" > /tmp/science_ts_probe.ts 2>/tmp/science_ts_probe.err || true
ls -la /tmp/science_ts_probe.ts
wc -c /tmp/science_ts_probe.ts
echo "=== err ==="
cat /tmp/science_ts_probe.err | tail -30
echo "=== head ==="
od -An -tx1 /tmp/science_ts_probe.ts | head -2
