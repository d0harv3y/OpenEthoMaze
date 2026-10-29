#!/bin/bash
set +e
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)
HOST="${1:-10.248.238.167}"
ssh "${KEY[@]}" "admin@$HOST" 'bash -s' <<'REMOTE'
set +e
hostname
echo "=== iface ==="
for d in usb0 wlan0; do
  echo -n "$d carrier="; cat /sys/class/net/$d/carrier 2>/dev/null || echo missing
  echo -n "$d oper="; cat /sys/class/net/$d/operstate 2>/dev/null || echo missing
done
ip -4 -br a
ip -4 route | head -8
echo "=== broker / link_state ==="
cat /var/lib/bhvr/broker.env 2>/dev/null || echo no_broker
cat /var/lib/bhvr/link_state.json 2>/dev/null || echo no_var_link
cat ~/.cache/bhvr/link_state.json 2>/dev/null || echo no_cache_link
echo "=== USB_DOWN default in binary ==="
grep -n 'USB_DOWN_BEFORE_WIFI_S' /usr/local/bin/bhvr-cam-announce | head -3
echo "=== run announce (may need sudo for broker write) ==="
sudo -n python3 /usr/local/bin/bhvr-cam-announce 2>&1 || python3 /usr/local/bin/bhvr-cam-announce 2>&1
REMOTE
