#!/bin/bash
# Download johnvansickle static armhf ffmpeg on NVR; install to cam via USB SSH.
set -euo pipefail
CAM="${1:-admin@192.168.7.27}"
SSH=(ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)
SCP=(scp -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)
if [[ -f "$HOME/.ssh/id_ed25519_bhvr" ]]; then
  SSH+=(-i "$HOME/.ssh/id_ed25519_bhvr")
  SCP+=(-i "$HOME/.ssh/id_ed25519_bhvr")
fi

echo "=== cleanup cam apt / restore usb0 ==="
"${SSH[@]}" "$CAM" 'sudo -n pkill -9 apt-get 2>/dev/null || true; sudo -n pkill -9 apt 2>/dev/null || true; sudo -n pkill -9 dpkg 2>/dev/null || true; sudo -n ip route add default via 192.168.7.1 dev usb0 metric 100 2>/dev/null || true; sudo -n networkctl reconfigure usb0 2>/dev/null || true; true'

WORKDIR=/tmp/ffmpeg-static-armhf
mkdir -p "$WORKDIR"
cd "$WORKDIR"
if [[ ! -x "$WORKDIR/ffmpeg" ]]; then
  echo "=== download static armhf ffmpeg (NVR side) ==="
  curl -fL --retry 3 -o ffmpeg-armhf.tar.xz \
    "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-armhf-static.tar.xz"
  tar -xf ffmpeg-armhf.tar.xz
  # tarball has one top-level dir
  BIN=$(find "$WORKDIR" -type f -name ffmpeg | head -1)
  cp -f "$BIN" "$WORKDIR/ffmpeg"
  chmod +x "$WORKDIR/ffmpeg"
fi
ls -la "$WORKDIR/ffmpeg"
"$WORKDIR/ffmpeg" -version | head -1 || true

echo "=== install on cam ==="
"${SCP[@]}" "$WORKDIR/ffmpeg" "${CAM}:/tmp/ffmpeg"
"${SSH[@]}" "$CAM" 'sudo -n install -m 0755 /tmp/ffmpeg /usr/local/bin/ffmpeg; command -v ffmpeg; ffmpeg -version | head -1; ls -la ~/bhvr-cam/scripts/live_udp_mpegts.sh 2>/dev/null || true'

CFG=/home/admin/bhvr-kiosk/config.yaml
if [[ -f "$CFG" ]]; then
  echo "=== kiosk → udp 720p30 ==="
  python3 - <<'PY'
from pathlib import Path
p = Path("/home/admin/bhvr-kiosk/config.yaml")
lines = p.read_text().splitlines(True)
out = []
in_preview = False
for line in lines:
    if line.startswith("preview:"):
        in_preview = True
        out.append(line)
        continue
    if in_preview and line and not line[0].isspace():
        in_preview = False
    if in_preview:
        key = line.strip().split(":", 1)[0]
        repl = {
            "width": "  width: 1280\n",
            "height": "  height: 720\n",
            "fps_idle": "  fps_idle: 30\n",
            "fps_record": "  fps_record: 30\n",
            "bitrate_kbps": "  bitrate_kbps: 2500\n",
            "buffer_count": "  buffer_count: 2\n",
            "transport": "  transport: udp\n",
            "nvr_host": "  nvr_host: 192.168.7.1\n",
            "udp_port": "  udp_port: 15550\n",
        }
        if key in repl:
            line = repl[key]
    out.append(line)
p.write_text("".join(out))
print("".join(out))
PY
fi
echo DONE
