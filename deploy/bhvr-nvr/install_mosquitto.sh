#!/bin/bash
# Install Mosquitto on bhvr-nvr*. Beacon is on-demand (kiosk button / systemctl),
# not a continuous spam service.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TREE="$SCRIPT_DIR"
if [[ ! -d "$TREE/scripts" ]]; then
  TREE="$(cd "$SCRIPT_DIR/.." && pwd)/bhvr-nvr"
fi

apt-get update
apt-get install -y --no-install-recommends mosquitto mosquitto-clients python3

install -d /etc/mosquitto/conf.d
cat >/etc/mosquitto/conf.d/bhvr.conf <<'EOF'
# bhvr discovery — closed lab LAN (wsu-iot). No auth for v0.
listener 1883
allow_anonymous true
persistence false
EOF

install -m 0755 "$TREE/scripts/broker_beacon.py" /usr/local/bin/bhvr-broker-beacon
install -m 0644 "$TREE/systemd/bhvr-broker-beacon.service" /etc/systemd/system/

systemctl enable --now mosquitto
systemctl daemon-reload
# Do NOT enable continuous beacon — use: sudo systemctl start bhvr-broker-beacon
systemctl disable bhvr-broker-beacon.service 2>/dev/null || true

echo "Mosquitto :1883 ready. Beacon is one-shot:"
echo "  sudo systemctl start bhvr-broker-beacon"
echo "  # or kiosk button POST /api/beacon"
ip -4 -br a
echo "Watch cams: mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/+/state' -v"
