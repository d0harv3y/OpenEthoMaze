#!/bin/bash
# Remove manual MQTT_BROKER override so Invite/UDP cache is authoritative.
# Run on the cam:  sudo bash clean_broker_override.sh
set -euo pipefail

ENV=/etc/bhvr-cam.env
if [[ ! -f "$ENV" ]]; then
  echo "no $ENV"
  exit 0
fi

if grep -qE '^[[:space:]]*MQTT_BROKER=' "$ENV"; then
  # shellcheck disable=SC2016
  sed -i -E 's/^[[:space:]]*MQTT_BROKER=.*/# MQTT_BROKER=  (cleared; use \/var\/lib\/bhvr\/broker.env from Invite)/' "$ENV"
  echo "cleared MQTT_BROKER= lines in $ENV"
else
  echo "no MQTT_BROKER= override present"
fi

echo "--- $ENV ---"
cat "$ENV"
echo "--- broker cache ---"
cat /var/lib/bhvr/broker.env 2>/dev/null || echo "(no broker.env yet — press Invite)"
echo "restart announce once from cache only:"
systemctl start bhvr-cam-announce.service || true
