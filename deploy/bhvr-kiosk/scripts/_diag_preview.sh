#!/bin/bash
set -euo pipefail
echo "=== nvr health (3s) ==="
curl -s --max-time 3 http://127.0.0.1:8080/api/health || echo "health_timeout"
echo
echo "=== preview cfg ==="
python3 - <<'PY'
import yaml
from pathlib import Path
print(yaml.safe_load(Path("/home/admin/bhvr-kiosk/config.yaml").read_text()).get("preview"))
PY
echo "=== udp 15550 ==="
ss -ulnp | grep 15550 || echo none
echo "=== procs ==="
pgrep -af 'uvicorn|ffmpeg|rpicam|live_udp|ssh.*bhvr-cam' || true
echo "=== cam via ssh ==="
ssh -i /home/admin/.ssh/id_ed25519_bhvr -o BatchMode=yes -o ConnectTimeout=8 admin@10.248.235.74 '
hostname
command -v ffmpeg
command -v rpicam-vid
pgrep -af "rpicam|ffmpeg|live_udp" || echo no_pub
ip -4 -br a
ls -la ~/bhvr-cam/scripts/live_udp_mpegts.sh
'
