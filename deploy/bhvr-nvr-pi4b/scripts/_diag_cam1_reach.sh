#!/bin/bash
set -uo pipefail
IP_WIFI=10.248.233.15
IP_USB=192.168.7.27
echo "=== ping wifi $IP_WIFI ==="
ping -c 3 -W 2 "$IP_WIFI" 2>&1 || true
echo "=== ping cam0 wifi (control) ==="
ping -c 2 -W 2 10.248.238.167 2>&1 || true
echo "=== arping/neigh ==="
ip neigh show "$IP_WIFI" 2>&1 || true
echo "=== long ssh wifi ==="
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=25 -o StrictHostKeyChecking=accept-new)
ssh "${KEY[@]}" "admin@$IP_WIFI" 'hostname; uptime; ip -br a; cat /var/lib/bhvr/broker.env 2>/dev/null; wc -c /usr/local/bin/bhvr-cam-announce; grep -n "MQTT_BROKER_WIFI\|_usb_link_usable\|zombie\|USB down" /usr/local/bin/bhvr-cam-announce | head -20; python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -8' 2>&1 | head -60
echo "=== mosquitto listen (5s) for cam1 ==="
timeout 5 mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/bhvr-cam1/state' -v 2>&1 || true
echo "=== usb ports / gadget ==="
for n in 0 1 2 3 4 5; do
  d=/sys/class/net/usb$n
  [[ -d $d ]] || continue
  echo "usb$n carrier=$(cat $d/carrier 2>/dev/null) $(ip -4 -br a show usb$n 2>/dev/null)"
done
