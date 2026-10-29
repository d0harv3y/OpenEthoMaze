#!/bin/bash
# Optional: stop avahi on cam1 (needs sudo). MQTT roster does not need mDNS.
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o ConnectTimeout=15)
CAM=admin@192.168.7.27
ssh -t "${KEY[@]}" "$CAM" 'bash -s' <<'EOS'
set -euo pipefail
echo "=== before ==="
ps -eo pcpu,comm --sort=-pcpu | head -8
sudo systemctl disable --now avahi-daemon.service avahi-daemon.socket 2>/dev/null || \
  sudo systemctl disable --now avahi-daemon 2>/dev/null || true
sleep 1
echo "=== after ==="
pgrep -a avahi || echo 'avahi gone'
ps -eo pcpu,comm --sort=-pcpu | head -8
EOS
