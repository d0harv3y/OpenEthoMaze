#!/bin/bash
# USB neigh + pin cam broker to USB gateway (192.168.7.1); try cam0 rescue paths.
set +e
echo "=== NVR USB / bridge ==="
ip -br a
echo "--- neigh br-bhvr ---"
ip neigh show dev br-bhvr 2>/dev/null || true
echo "--- usb ifaces ---"
for n in 0 1 2 3 4 5 6 7; do
  if [ -d "/sys/class/net/usb${n}" ]; then
    carr=$(cat "/sys/class/net/usb${n}/carrier" 2>/dev/null || echo '?')
    echo "usb${n} carrier=${carr} $(ip -4 -br a show "usb${n}" 2>/dev/null)"
  fi
done
echo "gadgets=$(lsusb | grep -c 1d6b:0104 || true)"
lsusb | grep -i '1d6b:0104\|Raspberry' || true

echo "=== sudo -n ==="
sudo -n true 2>&1 && echo passwordless_ok || echo passwordless_no

KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=6 -o StrictHostKeyChecking=accept-new)

pin_broker_usb() {
  local ip="$1"
  ssh "${KEY[@]}" "admin@$ip" 'bash -s' <<'REMOTE'
set -e
hostname
# Prefer USB NVR for MQTT so Invite WiFi IP does not steal announce/default-route optics.
echo 'MQTT_BROKER=192.168.7.1
MQTT_PORT=1883' | sudo tee /var/lib/bhvr/broker.env >/dev/null
sudo chmod 644 /var/lib/bhvr/broker.env
cat /var/lib/bhvr/broker.env
python3 /usr/local/bin/bhvr-cam-announce || true
REMOTE
}

echo "=== pin broker on reachable cams ==="
for ip in 192.168.7.27 192.168.7.28 192.168.7.31; do
  echo "-- pin $ip --"
  pin_broker_usb "$ip" 2>&1 | head -20
done

echo "=== cam0 reach scan ==="
for i in $(seq 20 50); do
  ip="192.168.7.$i"
  if ping -c1 -W1 "$ip" >/dev/null 2>&1; then
    host=$(ssh "${KEY[@]}" "admin@$ip" hostname 2>/dev/null || echo '?')
    echo "UP $ip host=$host"
  fi
done

echo "=== try cam0 via wifi IP from last known pattern ==="
# If cam0 has wlan, it may still answer MQTT; try common: announce over wifi
# Probe ARP for .41
ping -c1 -W1 192.168.7.41; echo ping41_exit=$?
ip neigh show 192.168.7.41 2>/dev/null || true

echo "=== restart dnsmasq/dhcp side? check br ==="
bridge link 2>/dev/null | head -20 || true

curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c 'import sys,json; [print(c["id"], c.get("ip"), c.get("online"), c.get("age_s")) for c in json.load(sys.stdin).get("cameras",[])]'
