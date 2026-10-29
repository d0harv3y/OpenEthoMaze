#!/bin/bash
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
# Kill hung soft-push SSH from NVR
pkill -f 'admin@192.168.7.28 bash -s' 2>/dev/null || true
pkill -f 'api/kiosk/usb-push' 2>/dev/null || true
ssh "${KEY[@]}" admin@192.168.7.28 bash -s <<'REMOTE'
sudo kill -9 13550 13551 13561 2>/dev/null || true
sudo pkill -9 -f 'systemctl enable --now bhvr-cam-broker' 2>/dev/null || true
echo KILLED
REMOTE
echo DONE
