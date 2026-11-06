#!/bin/bash
# Push smoothed HTU + 10s announce timer to cam0/cam1; reload timer; litmus.
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)

for pair in "bhvr-cam0:192.168.7.41" "bhvr-cam1:192.168.7.27"; do
  ID="${pair%%:*}"; IP="${pair#*:}"
  echo "=== $ID $IP ==="
  scp "${KEY[@]}" /tmp/bhvr-htu/htu21d.py /tmp/bhvr-htu/announce_mqtt.py /tmp/bhvr-htu/bhvr-cam-announce.timer "admin@${IP}:/tmp/"
  ssh "${KEY[@]}" "admin@${IP}" bash -s <<'REMOTE'
set -euxo pipefail
sudo tee /usr/local/lib/bhvr/htu21d.py >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-htu21d >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-announce >/dev/null </tmp/announce_mqtt.py
sudo tee /etc/systemd/system/bhvr-cam-announce.timer >/dev/null </tmp/bhvr-cam-announce.timer
sudo systemctl daemon-reload
sudo systemctl restart bhvr-cam-announce.timer
# Warm the ring with a few ticks (fast); shows SMA filling.
rm -f /run/bhvr/htu_ring.json 2>/dev/null || true
for i in 1 2 3; do
  python3 /usr/local/lib/bhvr/htu21d.py || true
done
python3 /usr/local/bin/bhvr-cam-announce || true
systemctl show bhvr-cam-announce.timer -p IntervalUSec -p OnUnitActiveUSec --no-pager || true
REMOTE
done
sleep 2
curl -sS http://127.0.0.1:8080/api/cams | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
for want in ("bhvr-cam0", "bhvr-cam1"):
    for c in d.get("cameras") or []:
        if c.get("id") == want:
            print(want, {k: c.get(k) for k in ("temp_c", "rh_pct", "ts")})
'
echo AVG_PUSH_DONE
