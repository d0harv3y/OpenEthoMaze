#!/bin/bash
# Push ~/bhvr-debs/*.deb to a USB-tethered cam and dpkg -i (needs cam sudo).
# Usage: bash _usb_push_debs_to_cam.sh [CAM_IP] [DEB_DIR]
set -euo pipefail
CAM_IP="${1:-192.168.7.27}"
DEB_DIR="${2:-$HOME/bhvr-debs}"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15)
CAM="admin@${CAM_IP}"

n="$(ls "$DEB_DIR"/*.deb 2>/dev/null | wc -l)"
if [[ "$n" -lt 1 ]]; then
  echo "no debs in $DEB_DIR" >&2
  exit 1
fi
echo "pushing $n debs → $CAM:~/bhvr-debs/"
ssh "${KEY[@]}" "$CAM" 'mkdir -p ~/bhvr-debs && rm -f ~/bhvr-debs/*.deb'
scp "${KEY[@]}" "$DEB_DIR"/*.deb "$CAM":~/bhvr-debs/
echo "installing (sudo)…"
if ssh "${KEY[@]}" "$CAM" 'sudo -n true' 2>/dev/null; then
  ssh "${KEY[@]}" "$CAM" 'sudo dpkg -i ~/bhvr-debs/*.deb'
else
  echo "cam has no passwordless sudo — run interactively:" >&2
  echo "  ssh -t ${KEY[*]} $CAM 'sudo dpkg -i ~/bhvr-debs/*.deb'" >&2
  exit 2
fi
ssh "${KEY[@]}" "$CAM" 'command -v ffmpeg; dpkg -l ffmpeg rpicam-apps 2>/dev/null | tail -5 || true'
echo "DONE"
