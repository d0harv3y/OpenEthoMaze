#!/bin/bash
# Push fixed htu21d.py; litmus cam0 + cam1 (need /dev/i2c + sensor).
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
SRC=/tmp/bhvr-htu/htu21d.py
test -f "$SRC"

for pair in "bhvr-cam0:192.168.7.41" "bhvr-cam1:192.168.7.27"; do
  ID="${pair%%:*}"
  IP="${pair#*:}"
  echo "=== $ID $IP ==="
  scp "${KEY[@]}" "$SRC" "admin@${IP}:/tmp/htu21d.py"
  ssh "${KEY[@]}" "admin@${IP}" bash -s <<'REMOTE'
set -euxo pipefail
sudo tee /usr/local/lib/bhvr/htu21d.py >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-htu21d >/dev/null </tmp/htu21d.py
ls -la /dev/i2c-1 2>/dev/null || echo NO_I2C
python3 /usr/local/lib/bhvr/htu21d.py || echo HTU_UNAVAILABLE
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
            print(want, {k: c.get(k) for k in ("temp_c", "rh_pct", "ts", "online")})
            break
'
echo RH_FIX_LITMUS_DONE
