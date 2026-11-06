#!/bin/bash
# Pi Zero W is ARMv6 — johnvansickle armhf (v7) SIGSEGVs; use armel static.
set -euo pipefail
CAM="${1:-admin@192.168.7.27}"
SSH=(ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new)
SCP=(scp -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new)
if [[ -f "$HOME/.ssh/id_ed25519_bhvr" ]]; then
  SSH+=(-i "$HOME/.ssh/id_ed25519_bhvr")
  SCP+=(-i "$HOME/.ssh/id_ed25519_bhvr")
fi

WORKDIR=/tmp/ffmpeg-static-armel
mkdir -p "$WORKDIR"
cd "$WORKDIR"
if [[ ! -x "$WORKDIR/ffmpeg" ]]; then
  echo "=== download static armel ffmpeg ==="
  curl -fL --retry 3 -o ffmpeg-armel.tar.xz \
    "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-armel-static.tar.xz"
  tar -xf ffmpeg-armel.tar.xz
  BIN=$(find "$WORKDIR" -type f -name ffmpeg | head -1)
  cp -f "$BIN" "$WORKDIR/ffmpeg"
  chmod +x "$WORKDIR/ffmpeg"
fi
"$WORKDIR/ffmpeg" -version | head -1

echo "=== push to cam ~/bin ==="
"${SCP[@]}" "$WORKDIR/ffmpeg" "${CAM}:/tmp/ffmpeg"
if [[ -f /tmp/live_udp_mpegts.sh ]]; then
  "${SCP[@]}" /tmp/live_udp_mpegts.sh "${CAM}:/tmp/live_udp_mpegts.sh"
fi
"${SSH[@]}" "$CAM" 'bash -s' <<'EOC'
set -euo pipefail
mkdir -p "$HOME/bin" "$HOME/bhvr-cam/scripts"
cp /tmp/ffmpeg "$HOME/bin/ffmpeg"
chmod +x "$HOME/bin/ffmpeg"
"$HOME/bin/ffmpeg" -version | head -1
if [[ -f /tmp/live_udp_mpegts.sh ]]; then
  sed 's/\r$//' /tmp/live_udp_mpegts.sh > "$HOME/bhvr-cam/scripts/live_udp_mpegts.sh"
  chmod +x "$HOME/bhvr-cam/scripts/live_udp_mpegts.sh"
fi
ls -la "$HOME/bin/ffmpeg" "$HOME/bhvr-cam/scripts/live_udp_mpegts.sh"
EOC
echo DONE
