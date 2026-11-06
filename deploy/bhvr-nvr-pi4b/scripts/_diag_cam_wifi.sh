#!/bin/bash
# Run on NVR: bash _diag_cam_wifi.sh [cam_ip]
set -euo pipefail
CAM="${1:-admin@192.168.7.27}"
SSH=(ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=8)
if [[ -f "$HOME/.ssh/id_ed25519_bhvr" ]]; then
  SSH+=(-i "$HOME/.ssh/id_ed25519_bhvr")
fi
"${SSH[@]}" "$CAM" 'bash -s' <<'EOC'
set +e
echo ===links===
ip -br link
ip -br a
echo ===rfkill===
rfkill list
echo ===nm===
nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev status
nmcli -t -f NAME,TYPE,DEVICE connection show
echo ===wifi-scan===
nmcli -f IN-USE,SSID,SIGNAL,SECURITY dev wifi list 2>&1 | head -25
echo ===country===
raspi-config nonint get_wifi_country 2>&1
echo ===conn-files===
ls -la /etc/NetworkManager/system-connections/ 2>&1
for f in /etc/NetworkManager/system-connections/*; do
  [ -f "$f" ] || continue
  echo "-- $(basename "$f") --"
  grep -E '^(id|type|ssid|autoconnect|interface-name)=' "$f" 2>/dev/null
done
echo ===nm-log===
journalctl -u NetworkManager -b --no-pager 2>&1 | grep -iE 'wlan0|wifi|wpa|fail|deny|auth|ssid|error|No secrets|disconnected' | tail -40
echo ===net-status===
cat /boot/firmware/bhvr-net-status.txt 2>/dev/null || cat /boot/bhvr-net-status.txt 2>/dev/null || echo '(none)'
echo ===firstrun-grep===
grep -iE 'wlan|wifi|ipv4|WARN|fail' /boot/firmware/bhvr-firstrun.log 2>/dev/null | tail -30 \
  || grep -iE 'wlan|wifi|ipv4|WARN|fail' /boot/bhvr-firstrun.log 2>/dev/null | tail -30 \
  || echo '(no firstrun log)'
EOC
