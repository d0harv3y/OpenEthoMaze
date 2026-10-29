#!/bin/bash
set -uo pipefail
# Install fixed cam script, pin kiosk config, smoke UDP, restart uvicorn.
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74

scp -i "$KEY" -o BatchMode=yes /tmp/live_udp_mpegts.sh "admin@$CAM:~/bhvr-cam/scripts/live_udp_mpegts.sh"
ssh -i "$KEY" -o BatchMode=yes "admin@$CAM" 'chmod +x ~/bhvr-cam/scripts/live_udp_mpegts.sh; sed -n "24,34p" ~/bhvr-cam/scripts/live_udp_mpegts.sh'

python3 - <<'PY'
import yaml
from pathlib import Path
p = Path("/home/admin/bhvr-kiosk/config.yaml")
cfg = yaml.safe_load(p.read_text()) or {}
prev = dict(cfg.get("preview") or {})
prev["transport"] = "mpegts"
prev["udp_port"] = 15550
prev["nvr_host"] = "10.248.238.22"
cfg["preview"] = prev
p.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))
print("preview=", prev)
PY

pkill -f 'uvicorn app.main' 2>/dev/null || true
sleep 1

echo "=== smoke UDP ==="
bash /home/admin/bhvr-kiosk/_smoke_udp.sh || bash /tmp/_smoke_udp.sh

echo "=== start kiosk ==="
cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2
curl -s --max-time 3 http://127.0.0.1:8080/api/health || echo health_fail
