#!/bin/bash
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15)

echo "=== NVR forward ==="
sysctl net.ipv4.ip_forward || true
# Try enable forward + MASQUERADE if passwordless sudo
if sudo -n true 2>/dev/null; then
  sudo -n sysctl -w net.ipv4.ip_forward=1 || true
  WAN=$(ip -4 route show default | awk '{print $5; exit}')
  if [[ -n "${WAN:-}" ]]; then
    sudo -n iptables -t nat -C POSTROUTING -o "$WAN" -j MASQUERADE 2>/dev/null \
      || sudo -n iptables -t nat -A POSTROUTING -o "$WAN" -j MASQUERADE || true
    sudo -n iptables -C FORWARD -i usb0 -o "$WAN" -j ACCEPT 2>/dev/null \
      || sudo -n iptables -A FORWARD -i usb0 -o "$WAN" -j ACCEPT || true
    sudo -n iptables -C FORWARD -i "$WAN" -o usb0 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null \
      || sudo -n iptables -A FORWARD -i "$WAN" -o usb0 -m state --state RELATED,ESTABLISHED -j ACCEPT || true
    echo "NAT via $WAN"
  fi
else
  echo "NOTE: no passwordless sudo on NVR — cannot enable NAT"
fi

ssh "${KEY[@]}" admin@192.168.7.27 'bash -s' <<'EOF'
set -euxo pipefail
ip -4 -br a
ip -4 route || true
sudo -n true 2>/dev/null && echo cam_sudo_ok || echo cam_no_sudo
# Point default at USB NVR
ip route del default 2>/dev/null || true
ip route add default via 192.168.7.1 dev usb0 || true
printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\n' | sudo tee /etc/resolv.conf >/dev/null || \
  printf 'nameserver 1.1.1.1\n' > /tmp/resolv.conf
ping -c1 -W3 1.1.1.1 || ping -c1 -W3 192.168.7.1
curl -sS -m 10 -o /dev/null -w "raspbian=%{http_code}\n" http://raspbian.raspberrypi.com/raspbian/ || echo curl_fail
dpkg --print-architecture
command -v ffmpeg || ls ~/bin/ffmpeg || echo no_ffmpeg
command -v rpicam-vid
EOF
