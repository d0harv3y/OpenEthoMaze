#!/bin/bash
set -uo pipefail
ip -br a show usb0
echo ---
ip neigh show dev usb0 || true
echo ---
networkctl status usb0 2>&1 | head -40
echo ---
echo "ping sweep 192.168.7.2-20"
for i in $(seq 2 20); do
  if ping -c1 -W1 "192.168.7.$i" >/dev/null 2>&1; then
    echo "UP 192.168.7.$i"
  fi
done
echo ---
echo "MQTT (3s):"
timeout 3 mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/+/state' -v 2>&1 || true
echo ---
curl -s --max-time 2 http://127.0.0.1:8080/api/health || true
echo
