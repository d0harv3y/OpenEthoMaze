#!/bin/bash
set +e
echo "=== networkctl br-bhvr ==="
networkctl status br-bhvr 2>&1 | head -45
echo "=== networkctl ==="
networkctl 2>&1 | head -25
echo "=== neigh br-bhvr ==="
ip neigh show dev br-bhvr
echo "=== ping USB ==="
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  if ping -c 1 -W 1 "$ip" >/dev/null 2>&1; then echo "OK $ip"; else echo "FAIL $ip"; fi
done
echo "=== mqtt 6s ==="
timeout 6 mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/+/state' -v 2>&1 | head -30
echo "=== cam1 via wifi ==="
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
ssh "${KEY[@]}" admin@10.248.233.15 bash -s <<'REMOTE'
hostname
ip -br a
echo '--- routes ---'
ip route
echo '--- ping br ---'
ping -c 2 -W 1 192.168.7.1 2>&1 | tail -5
echo '--- gadget ---'
systemctl is-active bhvr-cam-usb-gadget.service
systemctl is-active bhvr-cam-usb0-dhcp.service
journalctl -u bhvr-cam-usb-gadget -b --no-pager -n 20
journalctl -u bhvr-cam-usb0-dhcp -b --no-pager -n 15
REMOTE
echo "=== cam3 via wifi ==="
ssh "${KEY[@]}" admin@10.248.235.74 bash -s <<'REMOTE'
hostname
ip -br a
ping -c 2 -W 1 192.168.7.1 2>&1 | tail -5
systemctl is-active bhvr-cam-usb-gadget.service
REMOTE
echo "=== look for cam0/2 wifi ==="
# ARP/neigh on wlan + recent mqtt already; try nmap-ish ping sweep light
ip neigh | grep -E '^10\.248\.' | head -40
echo DONE
