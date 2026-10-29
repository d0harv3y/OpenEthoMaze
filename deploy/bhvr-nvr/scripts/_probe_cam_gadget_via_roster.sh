#!/bin/bash
# For each MQTT cam: is USB gadget up? (WiFi SSH OK)
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8)
mapfile -t rows < <(curl -sS -m 5 http://127.0.0.1:8080/api/cams \
  | python3 -c 'import sys,json; d=json.load(sys.stdin);
[print(c["id"], c["ip"]) for c in d.get("cameras",[])]')

for row in "${rows[@]}"; do
  id=${row%% *}
  ip=${row#* }
  echo "======== $id @ $ip ========"
  # Clear stale host keys for re-imaged cams
  ssh-keygen -f "$HOME/.ssh/known_hosts" -R "$ip" >/dev/null 2>&1 || true
  if ! ssh "${KEY[@]}" "admin@$ip" 'bash -s' <<'EOS'
set -uo pipefail
hostname
echo "--- overlays ---"
grep -E '^\s*dtoverlay=dwc2' /boot/firmware/config.txt /boot/config.txt 2>/dev/null || echo 'no dwc2 line'
echo "--- gadget unit ---"
systemctl is-enabled bhvr-cam-usb-gadget.service 2>&1 || true
systemctl is-active bhvr-cam-usb-gadget.service 2>&1 || true
echo "--- udc / usb0 ---"
ls /sys/class/udc 2>/dev/null || echo 'no UDC'
ip -br a | grep -E 'usb0|wlan0' || true
ip -4 route | head -5
echo "--- gadget product ---"
cat /sys/kernel/config/usb_gadget/*/strings/0x409/product 2>/dev/null || echo 'configfs product n/a'
EOS
  then
    echo "SSH FAILED $id"
  fi
  echo
done
