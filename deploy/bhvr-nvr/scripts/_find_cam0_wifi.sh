#!/bin/bash
# Find bhvr-cam0 on WSU-IoT (USB gadget missing — only 3 CDC devices).
set +e
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=3 -o StrictHostKeyChecking=accept-new
     -o UserKnownHostsFile=/dev/null)

echo "=== gadgets (want 4) ==="
lsusb | grep -c 1d6b:0104

echo "=== ping-sweep a slice of IoT for bhvr-cam0 (parallel) ==="
# Prior /20 is huge; sample .224-.239 last octets that cams used recently + neighbors
cands=()
for base in 229 235 238 230 231 232 233 234 236 237; do
  for last in $(seq 1 254); do
    cands+=("10.248.${base}.${last}")
  done
done
# Too big — narrow: use ip neigh on wlan0 + recent cam wifi IPs ±20
neigh=$(ip neigh show dev wlan0 | awk '/REACHABLE|STALE|DELAY/{print $1}')
echo "wlan neigh: $neigh"
targets="$neigh 10.248.229.141 10.248.235.74 10.248.238.22"
# expand ±30 around known cam wifi hosts
for seed in 10.248.229.141 10.248.235.74; do
  a=$(echo "$seed" | cut -d. -f3)
  b=$(echo "$seed" | cut -d. -f4)
  for d in $(seq $((b-40)) $((b+40))); do
    [ "$d" -ge 1 ] && [ "$d" -le 254 ] && targets="$targets 10.248.${a}.${d}"
  done
done
# also scan .238.* quickly (NVR subnet slice)
for d in $(seq 1 254); do targets="$targets 10.248.238.$d"; done

found=""
uniq_targets=$(echo $targets | tr ' ' '\n' | sort -u)
echo "probing $(echo "$uniq_targets" | wc -l) addresses..."
# parallel ping then ssh hostname
echo "$uniq_targets" | xargs -P 40 -I{} bash -c 'ping -c1 -W1 {} >/dev/null 2>&1 && echo UP {}' 2>/dev/null | tee /tmp/iot_up.txt

while read -r _ ip; do
  [ -z "$ip" ] && continue
  h=$(ssh "${KEY[@]}" "admin@$ip" 'hostname' 2>/dev/null || true)
  echo "ssh $ip -> ${h:-fail}"
  if [ "$h" = "bhvr-cam0" ]; then
    found=$ip
    echo "FOUND_CAM0 $ip"
    ssh "${KEY[@]}" "admin@$ip" 'ip -4 -br a; ip -4 route | head -8; cat /var/lib/bhvr/broker.env 2>/dev/null; rfkill list; nmcli -t -f DEVICE,STATE dev status'
    break
  fi
done < /tmp/iot_up.txt

if [ -z "$found" ]; then
  echo "CAM0_WIFI_NOT_FOUND — reseat USB or power-cycle hub port; MQTT online is WiFi announce with stale usb IP"
fi
