#!/bin/bash
# Push live_udp script + install ffmpeg on cam (USB preferred), set kiosk to udp 720p30.
# Usage on NVR: bash push_cam_ffmpeg_udp.sh [admin@192.168.7.27]
set -euo pipefail
CAM="${1:-admin@192.168.7.27}"
SSH=(ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)
SCP=(scp -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)
if [[ -f "$HOME/.ssh/id_ed25519_bhvr" ]]; then
  SSH+=(-i "$HOME/.ssh/id_ed25519_bhvr")
  SCP+=(-i "$HOME/.ssh/id_ed25519_bhvr")
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Prefer staged tree, else sibling checkout
UDP_SRC=""
for c in \
  /tmp/bhvr-cam-dhcp/scripts/live_udp_mpegts.sh \
  "$HOME/bhvr-cam/scripts/live_udp_mpegts.sh" \
  "$SCRIPT_DIR/../../bhvr-cam/scripts/live_udp_mpegts.sh"
do
  [[ -f "$c" ]] && UDP_SRC="$c" && break
done
if [[ -z "$UDP_SRC" ]]; then
  echo "missing live_udp_mpegts.sh — scp from laptop first" >&2
  exit 1
fi
sed 's/\r$//' "$UDP_SRC" > /tmp/live_udp_mpegts.sh
chmod +x /tmp/live_udp_mpegts.sh

echo "=== push UDP script ==="
"${SSH[@]}" "$CAM" 'mkdir -p ~/bhvr-cam/scripts'
# tar|ssh avoids IPv6 scp colon issues if CAM is link-local
tar -C /tmp -czf - live_udp_mpegts.sh | "${SSH[@]}" "$CAM" 'tar -C ~/bhvr-cam/scripts -xzf - && chmod +x ~/bhvr-cam/scripts/live_udp_mpegts.sh'

echo "=== install ffmpeg (prefer wlan for apt; restore usb0 default) ==="
"${SSH[@]}" "$CAM" 'bash -s' <<'EOC'
set -euo pipefail
if command -v ffmpeg >/dev/null; then
  ffmpeg -version | head -1
  exit 0
fi
USB_GW=$(ip -4 route show default dev usb0 2>/dev/null | awk '/via/{print $3; exit}' || true)
if [[ -n "${USB_GW:-}" ]]; then
  sudo -n ip route del default via "$USB_GW" dev usb0 || true
  echo "dropped usb0 default via $USB_GW for apt"
fi
printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\n' | sudo -n tee /etc/resolv.conf >/dev/null
export DEBIAN_FRONTEND=noninteractive
sudo -n apt-get -o Acquire::ForceIPv4=true update -qq || true
sudo -n apt-get -o Acquire::ForceIPv4=true install -y --no-install-recommends ffmpeg
if [[ -n "${USB_GW:-}" ]]; then
  sudo -n ip route add default via "$USB_GW" dev usb0 metric 100 || true
fi
sudo -n networkctl reconfigure usb0 2>/dev/null || true
command -v ffmpeg
ffmpeg -version | head -1
ip -4 route
EOC

CFG=/home/admin/bhvr-kiosk/config.yaml
if [[ -f "$CFG" ]]; then
  echo "=== kiosk preview → udp 720p30 ==="
  # crude but idempotent-ish
  sed -i 's/transport: .*/transport: udp/' "$CFG"
  sed -i 's/nvr_host: .*/nvr_host: 192.168.7.1/' "$CFG"
  # preview block geometry
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
    if in_preview and line and not line[0].isspace() and not line.startswith("preview:"):
        in_preview = False
    if in_preview:
        if line.strip().startswith("width:"):
            line = "  width: 1280\n"
        elif line.strip().startswith("height:"):
            line = "  height: 720\n"
        elif line.strip().startswith("fps_idle:"):
            line = "  fps_idle: 30\n"
        elif line.strip().startswith("fps_record:"):
            line = "  fps_record: 30\n"
        elif line.strip().startswith("bitrate_kbps:"):
            line = "  bitrate_kbps: 2500\n"
        elif line.strip().startswith("buffer_count:"):
            line = "  buffer_count: 2\n"
        elif line.strip().startswith("transport:"):
            line = "  transport: udp\n"
        elif line.strip().startswith("nvr_host:"):
            line = "  nvr_host: 192.168.7.1\n"
        elif line.strip().startswith("udp_port:"):
            line = "  udp_port: 15550\n"
    out.append(line)
p.write_text("".join(out))
print(p.read_text())
PY
fi

echo "=== smoke: cam has ffmpeg + script ==="
"${SSH[@]}" "$CAM" 'command -v ffmpeg; test -x ~/bhvr-cam/scripts/live_udp_mpegts.sh; ip -4 -br a'
echo "done — hard-refresh kiosk focus live (transport=udp)"
