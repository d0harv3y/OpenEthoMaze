#!/bin/bash
# Probe/fix cam0+cam2 over USB after reboot (silent on MQTT).
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)

probe() {
  local ip=$1
  echo "======== $ip ========"
  ssh "${KEY[@]}" "admin@$ip" bash -s <<'REMOTE'
set +e
hostname
echo "--- ifaces ---"
ip -br a
echo "--- broker ---"
cat /var/lib/bhvr/broker.env 2>/dev/null || echo no_broker_env
grep -E '^MQTT_BROKER|^#.*MQTT' /etc/bhvr-cam.env 2>/dev/null || true
echo "--- units ---"
systemctl is-active bhvr-cam-announce.timer
systemctl is-active bhvr-cam-announce.service
systemctl is-active bhvr-cam-broker-listen.service
systemctl is-active bhvr-cam-usb-gadget.service
echo "--- one-shot announce ---"
timeout -k 2 12 python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -5
echo "--- restart timer ---"
sudo /bin/systemctl restart bhvr-cam-announce.timer 2>&1 || true
REMOTE
}

probe 192.168.7.41
probe 192.168.7.31
echo "=== wait mqtt ==="
sleep 8
timeout 5 mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/+/state' -v 2>&1 | head -20 || true
curl -sS -m 5 http://127.0.0.1:8080/api/cams | python3 -c '
import sys,json
d=json.load(sys.stdin)
for c in d.get("cameras") or []:
  print(c.get("id"), c.get("online"), c.get("link"), c.get("ip"), (c.get("ips") or {}))
'
echo FIX_SILENT_DONE
