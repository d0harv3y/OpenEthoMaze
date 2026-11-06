#!/bin/bash
# Deploy 1 Hz HTU sampler + 10 s announce stats; refresh kiosk env_log/main.
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)

# Kiosk REC JSONL + MQTT ingest
if [[ -f /tmp/bhvr-htu/env_log.py ]]; then
  cp /tmp/bhvr-htu/env_log.py app/env_log.py
fi
if [[ -f /tmp/bhvr-htu/main.py ]]; then
  cp /tmp/bhvr-htu/main.py app/main.py
  # Restart uvicorn if we can find a unit; else kill+note (operator may run under screen).
  if systemctl --user restart bhvr-kiosk-web.service 2>/dev/null; then
    echo restarted_user_kiosk
  elif pgrep -f 'uvicorn app.main:app' >/dev/null; then
    echo "WARN: kiosk uvicorn running — restart manually to load main.py" >&2
  fi
fi

for pair in "bhvr-cam0:192.168.7.41" "bhvr-cam1:192.168.7.27"; do
  ID="${pair%%:*}"; IP="${pair#*:}"
  echo "=== $ID $IP ==="
  scp "${KEY[@]}" \
    /tmp/bhvr-htu/htu21d.py \
    /tmp/bhvr-htu/announce_mqtt.py \
    /tmp/bhvr-htu/bhvr-cam-htu-sample.service \
    /tmp/bhvr-htu/bhvr-cam-htu-sample.timer \
    /tmp/bhvr-htu/bhvr-cam-announce.timer \
    "admin@${IP}:/tmp/"
  ssh "${KEY[@]}" "admin@${IP}" bash -s <<'REMOTE'
set -euxo pipefail
sudo tee /usr/local/lib/bhvr/htu21d.py >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-htu21d >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-announce >/dev/null </tmp/announce_mqtt.py
sudo tee /etc/systemd/system/bhvr-cam-htu-sample.service >/dev/null </tmp/bhvr-cam-htu-sample.service
sudo tee /etc/systemd/system/bhvr-cam-htu-sample.timer >/dev/null </tmp/bhvr-cam-htu-sample.timer
sudo tee /etc/systemd/system/bhvr-cam-announce.timer >/dev/null </tmp/bhvr-cam-announce.timer
sudo systemctl daemon-reload
sudo systemctl enable --now bhvr-cam-htu-sample.timer
sudo systemctl restart bhvr-cam-announce.timer
# Warm ring ~3 s then show window stats
for i in 1 2 3; do python3 /usr/local/bin/bhvr-cam-htu21d sample || true; sleep 0.2; done
python3 /usr/local/bin/bhvr-cam-htu21d || true
python3 /usr/local/bin/bhvr-cam-announce || true
systemctl is-active bhvr-cam-htu-sample.timer || true
REMOTE
done
sleep 2
curl -sS http://127.0.0.1:8080/api/cams | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
for want in ("bhvr-cam0", "bhvr-cam1"):
    for c in d.get("cameras") or []:
        if c.get("id") == want:
            print(want, {k: c.get(k) for k in ("temp_c", "rh_pct", "env", "ts")})
'
echo HTU_1HZ_DONE
