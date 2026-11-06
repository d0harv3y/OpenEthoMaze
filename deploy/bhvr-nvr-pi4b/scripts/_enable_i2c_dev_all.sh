#!/bin/bash
# Install i2c-dev modules-load.d on online cams; reboot cam0 and litmus HTU.
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
mapfile -t IPS < <(curl -sS http://127.0.0.1:8080/api/cams | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
for c in d.get("cameras") or []:
    if c.get("online") and c.get("ip"):
        print(c["ip"], c.get("id",""))
')
CAM0_IP=""
for line in "${IPS[@]}"; do
  IP="${line%% *}"
  ID="${line#* }"
  echo "=== $ID $IP ==="
  ssh "${KEY[@]}" "admin@${IP}" bash -s <<'REMOTE' || true
set -euxo pipefail
echo i2c-dev | sudo tee /etc/modules-load.d/i2c-dev.conf
cat /etc/modules-load.d/i2c-dev.conf
REMOTE
  if [[ "$ID" == "bhvr-cam0" ]]; then
    CAM0_IP="$IP"
  fi
done

if [[ -z "$CAM0_IP" ]]; then
  echo "no cam0 online"
  exit 1
fi

ssh "${KEY[@]}" "admin@${CAM0_IP}" 'sudo systemctl reboot' || true
echo REBOOT_SENT
sleep 30
for i in $(seq 1 24); do
  if ssh "${KEY[@]}" "admin@${CAM0_IP}" 'echo UP'; then
    break
  fi
  echo "wait_$i"
  sleep 10
done

ssh "${KEY[@]}" "admin@${CAM0_IP}" bash -s <<'REMOTE'
set -euxo pipefail
lsmod | grep -i i2c || true
ls -la /dev/i2c-* 2>/dev/null || echo NO_I2C_DEV
python3 /usr/local/lib/bhvr/htu21d.py || echo HTU_UNAVAILABLE
sudo systemctl start bhvr-cam-announce.service || true
sleep 1
python3 /usr/local/bin/bhvr-cam-announce || true
REMOTE

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
