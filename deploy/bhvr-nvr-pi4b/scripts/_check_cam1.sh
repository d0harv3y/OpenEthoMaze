#!/bin/bash
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10)
ssh "${KEY[@]}" admin@192.168.7.27 <<'EOC'
hostname
ls -la /tmp/t.h264 ~/bin/ffmpeg
pgrep -af ffmpeg || echo no_ffmpeg
ping -c1 -W1 192.168.7.1 || true
ip -4 addr show usb0 | head -8
EOC
