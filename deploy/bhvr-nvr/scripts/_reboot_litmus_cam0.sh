#!/bin/bash
# Reboot cam0, wait for SSH, litmus HTU21D + announce + kiosk roster.
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)
CAM_IP="${CAM_IP:-192.168.7.41}"

ssh "${KEY[@]}" "admin@${CAM_IP}" 'sudo systemctl reboot' || true
echo REBOOT_SENT
sleep 25

for i in $(seq 1 18); do
  if ssh "${KEY[@]}" "admin@${CAM_IP}" 'echo UP'; then
    break
  fi
  echo "wait_$i"
  sleep 10
done

ssh "${KEY[@]}" "admin@${CAM_IP}" bash -s <<'REMOTE'
set -euxo pipefail
ls -la /dev/i2c-* 2>/dev/null || echo NO_I2C_DEV
python3 /usr/local/lib/bhvr/htu21d.py || echo HTU_UNAVAILABLE
sudo systemctl start bhvr-cam-announce.service || true
sleep 1
python3 /usr/local/bin/bhvr-cam-announce || true
REMOTE

cd "$HOME/bhvr-kiosk"
sleep 3
curl -sS http://127.0.0.1:8080/api/cams | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
for c in d.get("cameras") or []:
    if c.get("id") == "bhvr-cam0":
        keys = ("temp_c", "rh_pct", "ts", "online", "ip")
        print("cam0", {k: c.get(k) for k in keys})
        break
else:
    print("cam0_missing")
'
echo LITMUS_DONE
