#!/bin/bash
# From NVR: install ffmpeg on a tethered/WiFi cam (NOPASSWD apt via firstboot).
# Temporarily prefers wlan0 default so apt isn't trapped by usb0 (metric 100, no NAT).
set -euo pipefail
CAM="${1:-admin@192.168.7.27}"
SSH=(ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=15)
[[ -f "$HOME/.ssh/id_ed25519_bhvr" ]] && SSH+=(-i "$HOME/.ssh/id_ed25519_bhvr")

"${SSH[@]}" "$CAM" 'bash -s' <<'EOC'
set -euo pipefail
if command -v ffmpeg >/dev/null; then
  ffmpeg -version | head -1
  exit 0
fi
# Prefer campus WiFi for package fetch while usb0 has no uplink.
if ip -4 route show default dev wlan0 | grep -q .; then
  USB_GW=$(ip -4 route show default dev usb0 | awk '/via/{print $3; exit}')
  if [[ -n "${USB_GW:-}" ]]; then
    sudo -n ip route del default via "$USB_GW" dev usb0 || true
    echo "dropped usb0 default for apt (via $USB_GW)"
  fi
fi
printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\n' | sudo -n tee /etc/resolv.conf >/dev/null
sudo -n apt-get update -qq
sudo -n apt-get install -y --no-install-recommends ffmpeg
# Restore usb0 default (networkd / DHCP)
if [[ -n "${USB_GW:-}" ]]; then
  sudo -n ip route add default via "$USB_GW" dev usb0 metric 100 || true
fi
sudo -n networkctl reconfigure usb0 2>/dev/null || true
command -v ffmpeg
ffmpeg -version | head -1
EOC
