#!/bin/bash
# Install HTU21D announce bits on all online cams; enable i2c_arm (reboot needed).
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
for line in "${IPS[@]}"; do
  IP="${line%% *}"
  ID="${line#* }"
  echo "=== $ID $IP ==="
  scp "${KEY[@]}" /tmp/bhvr-htu/htu21d.py /tmp/bhvr-htu/announce_mqtt.py /tmp/bhvr-htu/bhvr-cam-announce.service "admin@${IP}:/tmp/" || continue
  ssh "${KEY[@]}" "admin@${IP}" bash -s <<'REMOTE' || true
set -euxo pipefail
sudo mkdir -p /usr/local/lib/bhvr
sudo tee /usr/local/lib/bhvr/htu21d.py >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-htu21d >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-announce >/dev/null </tmp/announce_mqtt.py
sudo tee /etc/systemd/system/bhvr-cam-announce.service >/dev/null </tmp/bhvr-cam-announce.service
sudo systemctl daemon-reload
# Enable I2C if missing (takes effect after reboot).
for cfg in /boot/firmware/config.txt /boot/config.txt; do
  if [[ -f "$cfg" ]] && ! grep -qE '^dtparam=i2c_arm=on' "$cfg"; then
    echo 'dtparam=i2c_arm=on' | sudo tee -a "$cfg"
    echo I2C_ENABLED_NEEDS_REBOOT
  fi
done
# Char nodes: dtparam loads bcm2835; i2c-dev creates /dev/i2c-*.
echo i2c-dev | sudo tee /etc/modules-load.d/i2c-dev.conf
ls -la /dev/i2c-* 2>/dev/null || echo NO_I2C_DEV_YET
python3 /tmp/htu21d.py || echo HTU_UNAVAILABLE_UNTIL_I2C
sudo systemctl start bhvr-cam-announce.service || true
REMOTE
done
echo PUSH_DONE
