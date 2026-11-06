#!/bin/bash
# Push temp-tolerant HTU reader + announce; refresh kiosk index; litmus cam0/1.
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)

# Kiosk tile (temp-only OK).
if [[ -f /tmp/bhvr-htu/index.html ]]; then
  cp /tmp/bhvr-htu/index.html app/templates/index.html
  sudo systemctl restart bhvr-kiosk.service || sudo systemctl restart maze-bhvr-kiosk.service || true
fi

for pair in "bhvr-cam0:192.168.7.41" "bhvr-cam1:192.168.7.27"; do
  ID="${pair%%:*}"; IP="${pair#*:}"
  echo "=== $ID $IP ==="
  scp "${KEY[@]}" /tmp/bhvr-htu/htu21d.py /tmp/bhvr-htu/announce_mqtt.py "admin@${IP}:/tmp/"
  ssh "${KEY[@]}" "admin@${IP}" bash -s <<'REMOTE'
set -euxo pipefail
sudo tee /usr/local/lib/bhvr/htu21d.py >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-htu21d >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-announce >/dev/null </tmp/announce_mqtt.py
python3 /usr/local/lib/bhvr/htu21d.py || true
python3 /usr/local/bin/bhvr-cam-announce || true
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
echo PARTIAL_DONE
