#!/bin/bash
# Abort hung apt; restore usb0 route; pin kiosk to annex_b @ 30fps (no ffmpeg).
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10)
ssh "${KEY[@]}" admin@192.168.7.27 'bash -s' <<'EOC'
set +e
sudo -n pkill -9 apt-get 2>/dev/null
sudo -n pkill -9 apt 2>/dev/null
sudo -n pkill -9 dpkg 2>/dev/null
command -v ffmpeg && ffmpeg -version | head -1 || echo NO_FFMPEG
# restore usb0 default if missing
if ! ip -4 route show default dev usb0 | grep -q .; then
  sudo -n ip route add default via 192.168.7.1 dev usb0 metric 100 || true
fi
sudo -n networkctl reconfigure usb0 2>/dev/null || true
ip -4 route
ip -br a
EOC

CFG=/home/admin/bhvr-kiosk/config.yaml
sed -i 's/transport: mpegts/transport: ssh_annex_b/' "$CFG"
sed -i 's/default_profile: 480p/default_profile: 720p/' "$CFG"
# ensure 30fps knobs (idempotent)
grep -q 'soft_fps: 30' "$CFG" || sed -i 's/soft_fps: .*/soft_fps: 30/' "$CFG"
grep -q 'fps_idle: 30' "$CFG" || sed -i 's/fps_idle: .*/fps_idle: 30/' "$CFG"
grep -q 'fps_record: 30' "$CFG" || sed -i 's/fps_record: .*/fps_record: 30/' "$CFG"
grep -E 'default_profile|transport|fps_|soft_fps|width|height|bitrate' "$CFG"

# smoke: 3s annex-B pull
rm -f /tmp/prev30.bin
timeout 6 curl -sS -o /tmp/prev30.bin -w "preview_bytes=%{size_download} http=%{http_code}\n" \
  "http://127.0.0.1:8080/api/preview/bhvr-cam1" || true
wc -c /tmp/prev30.bin 2>/dev/null || true
tail -5 /tmp/bhvr-preview-bhvr-cam1.log 2>/dev/null || true
