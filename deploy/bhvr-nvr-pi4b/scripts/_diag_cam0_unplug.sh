#!/bin/bash
# Why is cam0 still ONLINE · USB after unplug?
set +e
echo "=== roster ==="
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("id")=="bhvr-cam0":
        print({k:c.get(k) for k in ("online","age_s","ip","link","ips","ts")})
'

KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)

# Try WiFi IP from roster, then known
WIFI=$(curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("id")=="bhvr-cam0":
        ips=c.get("ips") or {}
        print(ips.get("wifi") or "")
        break
')
echo "roster wifi_ip=${WIFI:-none}"

probe() {
  local host="$1"
  echo "=== ssh $host ==="
  ssh "${KEY[@]}" "admin@$host" 'bash -s' <<'REMOTE'
set +e
hostname
date -u +%Y-%m-%dT%H:%M:%SZ
echo "--- carrier/oper ---"
for d in usb0 wlan0; do
  echo -n "$d carrier="; cat /sys/class/net/$d/carrier 2>/dev/null || echo missing
  echo -n "$d oper="; cat /sys/class/net/$d/operstate 2>/dev/null || echo missing
done
ip -4 -br a
ip -4 route | head -8
echo "--- broker.env ---"
cat /var/lib/bhvr/broker.env 2>/dev/null || echo none
echo "--- link_state ---"
cat /var/lib/bhvr/link_state.json 2>/dev/null || echo 'no /var/lib'
cat ~/.cache/bhvr/link_state.json 2>/dev/null || echo 'no ~/.cache'
echo "--- announce binary ---"
grep -n 'USB_DOWN_BEFORE_WIFI_S\|MQTT_BROKER_WIFI\|_sync_broker' /usr/local/bin/bhvr-cam-announce | head -10
echo "--- timer ---"
systemctl is-active bhvr-cam-announce.timer
journalctl -u bhvr-cam-announce.service -n 15 --no-pager
echo "--- manual announce ---"
sudo -n python3 /usr/local/bin/bhvr-cam-announce 2>&1 || python3 /usr/local/bin/bhvr-cam-announce 2>&1
REMOTE
}

if [[ -n "$WIFI" ]]; then
  probe "$WIFI"
else
  probe "10.248.238.167"
fi

echo "=== USB .41 (expect fail if unplugged) ==="
ping -c1 -W1 192.168.7.41; echo ping41=$?
ip neigh show 192.168.7.41 2>/dev/null || true
echo "gadgets=$(lsusb | grep -c 1d6b:0104 || true)"
