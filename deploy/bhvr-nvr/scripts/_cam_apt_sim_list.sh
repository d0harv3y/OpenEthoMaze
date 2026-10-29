#!/bin/bash
# Print packages apt would newly install for ffmpeg + rpicam-apps on cam (USB).
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15)
ssh "${KEY[@]}" admin@192.168.7.27 \
  'apt-get install -s --no-install-recommends ffmpeg rpicam-apps 2>/dev/null' \
  | awk '/^Inst /{print $2}' | sort -u
