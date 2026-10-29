#!/bin/bash
# Fix Pi Zero: comment otg_mode=1, force dwc2 peripheral, reboot (NOPASSWD tee/systemctl).
# Usage on NVR: bash _fix_cam_otg_mode.sh [ip ...]
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=12)
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${HERE}/_fix_cam_otg_mode.py"
[[ -f "$PY" ]] || PY=/tmp/_fix_cam_otg_mode.py
IPS=("$@")
if ((${#IPS[@]} == 0)); then
  IPS=(10.248.229.141 10.248.235.74)
fi

for ip in "${IPS[@]}"; do
  echo "======== $ip ========"
  scp "${KEY[@]}" "$PY" "admin@$ip:/tmp/_fix_cam_otg_mode.py"
  ssh "${KEY[@]}" "admin@$ip" \
    'python3 /tmp/_fix_cam_otg_mode.py && sudo tee /boot/firmware/config.txt < /tmp/config.txt.bhvr >/dev/null && grep -nE "otg_mode|dwc2" /boot/firmware/config.txt && sudo systemctl reboot'
  echo "reboot issued for $ip"
done
echo "Wait ~60s, then on NVR: lsusb | grep 1d6b:0104 ; ip neigh | grep 192.168.7"
