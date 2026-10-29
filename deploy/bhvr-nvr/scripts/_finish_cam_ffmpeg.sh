#!/bin/bash
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=25)
echo "=== neigh / ports ==="
ip neigh show dev usb0 || true
nc -vz -w 5 192.168.7.27 22 2>&1 || true
ping -c1 -W2 192.168.7.27 || true

echo "=== try IPv4 SSH ==="
if ssh "${KEY[@]}" admin@192.168.7.27 'echo ipv4_ok; hostname'; then
  CAM=admin@192.168.7.27
else
  echo "IPv4 SSH failed; try link-local"
  CAM='admin@fe80::27:ebff:fe96:f5bb%usb0'
  ssh "${KEY[@]}" "$CAM" 'echo ipv6_ok; hostname' || {
    echo "cam SSH dead — power-cycle cam1 USB, then re-run"
    exit 1
  }
fi

echo "=== install ffmpeg to ~/bin ==="
# copy from NVR workdir if present
if [[ -x /tmp/ffmpeg-static-armhf/ffmpeg ]]; then
  scp "${KEY[@]}" /tmp/ffmpeg-static-armhf/ffmpeg "${CAM}:/tmp/ffmpeg"
fi
# script
if [[ -f /tmp/live_udp_mpegts.sh ]]; then
  scp "${KEY[@]}" /tmp/live_udp_mpegts.sh "${CAM}:/tmp/live_udp_mpegts.sh"
fi

ssh "${KEY[@]}" "$CAM" 'bash -s' <<'EOC'
set -euo pipefail
mkdir -p "$HOME/bin" "$HOME/bhvr-cam/scripts"
if [[ -f /tmp/ffmpeg ]]; then
  cp /tmp/ffmpeg "$HOME/bin/ffmpeg"
  chmod +x "$HOME/bin/ffmpeg"
fi
if [[ -f /tmp/live_udp_mpegts.sh ]]; then
  sed 's/\r$//' /tmp/live_udp_mpegts.sh > "$HOME/bhvr-cam/scripts/live_udp_mpegts.sh"
  chmod +x "$HOME/bhvr-cam/scripts/live_udp_mpegts.sh"
fi
"$HOME/bin/ffmpeg" -version | head -1
ls -la "$HOME/bin/ffmpeg" "$HOME/bhvr-cam/scripts/live_udp_mpegts.sh"
# quick mux smoke (2s)
timeout 8 bash "$HOME/bhvr-cam/scripts/live_udp_mpegts.sh" 192.168.7.1 15550 640 480 15 800 2 \
  >/tmp/udp-smoke.log 2>&1 &
sleep 5
kill %1 2>/dev/null || true
tail -20 /tmp/udp-smoke.log || true
EOC

echo "=== kiosk config check ==="
grep -E 'transport|fps_idle|nvr_host|width' /home/admin/bhvr-kiosk/config.yaml | head -20
echo "DONE — hard-refresh kiosk focus live"
