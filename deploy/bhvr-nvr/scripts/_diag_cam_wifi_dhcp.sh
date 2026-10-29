#!/bin/bash
set -euo pipefail
CAM="${1:-admin@192.168.7.27}"
SSH=(ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=8)
[[ -f "$HOME/.ssh/id_ed25519_bhvr" ]] && SSH+=(-i "$HOME/.ssh/id_ed25519_bhvr")
"${SSH[@]}" "$CAM" 'bash -s' <<'EOC'
set +e
echo ===links===
ip -br a
echo ===iw-link===
iw dev wlan0 link
echo ===nm-active===
nmcli -t -f NAME,DEVICE,TYPE,STATE connection show --active
nmcli -t -f NAME,UUID,TYPE,DEVICE connection show
echo ===mac===
cat /sys/class/net/wlan0/address
echo ===nm-dhcp===
journalctl -u NetworkManager -b --no-pager | grep -iE 'wlan0|dhcp|timeout|lease|IP config|activation|WSU|no available' | tail -60
EOC
