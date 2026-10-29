#!/bin/bash
# Deploy HTU21D announce + kiosk env tile/jsonl.
set -euxo pipefail
SRC=/tmp/bhvr-htu
DEST="$HOME/bhvr-kiosk"
cp -f "$SRC/env_log.py" "$DEST/app/env_log.py"
cp -f "$SRC/main.py" "$DEST/app/main.py"
cp -f "$SRC/index.html" "$DEST/app/templates/index.html"
mkdir -p "$DEST/tests"
cp -f "$SRC/test_env_jsonl.py" "$DEST/tests/test_env_jsonl.py"
cd "$DEST"
.venv/bin/python -c 'from app.env_log import append_env_jsonl; print("env_log_ok")'
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 25); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.4
done
curl -sS http://127.0.0.1:8080/api/cams | head -c 400; echo
echo KIOSK_OK

# Push cam scripts to first online cam if any
CAM_IP=$(curl -sS http://127.0.0.1:8080/api/cams | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
for c in d.get("cameras") or []:
    if c.get("online") and c.get("ip"):
        print(c["ip"]); break
')
if [[ -n "${CAM_IP:-}" ]]; then
  KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
  scp "${KEY[@]}" "$SRC/htu21d.py" "$SRC/announce_mqtt.py" "$SRC/bhvr-cam-announce.service" "admin@${CAM_IP}:/tmp/"
  # Cam sudoers: NOPASSWD systemctl/tee/mkdir — install via tee (no chmod needed).
  ssh "${KEY[@]}" "admin@${CAM_IP}" bash -s <<'REMOTE'
set -euxo pipefail
sudo mkdir -p /usr/local/lib/bhvr
sudo tee /usr/local/lib/bhvr/htu21d.py >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-htu21d >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-announce >/dev/null </tmp/announce_mqtt.py
sudo tee /etc/systemd/system/bhvr-cam-announce.service >/dev/null </tmp/bhvr-cam-announce.service
sudo systemctl daemon-reload
python3 /tmp/htu21d.py || echo HTU_UNAVAILABLE
sudo systemctl start bhvr-cam-announce.service
sleep 2
journalctl -u bhvr-cam-announce.service -n 8 --no-pager || true
REMOTE
  echo CAM_LITMUS_DONE ip=$CAM_IP
else
  echo CAM_LITMUS_SKIP no_online_cam
fi
