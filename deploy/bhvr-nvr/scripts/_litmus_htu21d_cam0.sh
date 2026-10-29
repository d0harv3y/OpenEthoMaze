#!/bin/bash
set -euxo pipefail
CAM_IP="${1:-192.168.7.41}"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
scp "${KEY[@]}" /tmp/bhvr-htu/htu21d.py /tmp/bhvr-htu/announce_mqtt.py "admin@${CAM_IP}:/tmp/"
ssh "${KEY[@]}" "admin@${CAM_IP}" bash -s <<'REMOTE'
set -euxo pipefail
sudo mkdir -p /usr/local/lib/bhvr
sudo tee /usr/local/lib/bhvr/htu21d.py >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-htu21d >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-announce >/dev/null </tmp/announce_mqtt.py
python3 /tmp/htu21d.py || echo HTU_UNAVAILABLE
ls -la /dev/i2c-* 2>/dev/null || echo NO_I2C_DEV
sudo systemctl start bhvr-cam-announce.service
sleep 2
journalctl -u bhvr-cam-announce.service -n 6 --no-pager || true
REMOTE
curl -sS http://127.0.0.1:8080/api/cams | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
for c in d.get("cameras") or []:
    if c.get("id") == "bhvr-cam0":
        print("cam0", {k: c.get(k) for k in ("temp_c", "rh_pct", "ts", "online")})
        break
'
