#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10)
for ip in 10.248.229.141 10.248.235.74; do
  echo "======== $ip ========"
  ssh "${KEY[@]}" "admin@$ip" 'bash -s' <<'EOS'
hostname
echo "--- udc ---"
ls -la /sys/class/udc 2>&1 || true
echo "--- modules ---"
lsmod | grep -E 'dwc2|libcomposite|usb_f_ecm' || true
echo "--- status ---"
systemctl status bhvr-cam-usb-gadget.service --no-pager -l 2>&1 | tail -30
echo "--- journal ---"
journalctl -u bhvr-cam-usb-gadget.service -b --no-pager 2>&1 | tail -25
echo "--- vcgencmd otg ---"
vcgencmd get_config dtoverlay 2>/dev/null || true
cat /boot/firmware/config.txt | grep -nE 'dwc2|otg|dtoverlay' | head -20
EOS
  echo
done
echo '=== NVR hub ports ==='
lsusb -t | head -20
