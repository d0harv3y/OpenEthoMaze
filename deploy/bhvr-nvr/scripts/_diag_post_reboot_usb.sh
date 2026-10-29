#!/bin/bash
# Post-reboot: which cams on MQTT, USB L3, DHCP, gadget host.
set -euo pipefail
echo "=== clock ==="
date -u; uptime
echo "=== kiosk cams ==="
curl -sS -m 5 http://127.0.0.1:8080/api/cams | python3 -c '
import sys,json
d=json.load(sys.stdin)
for c in d.get("cameras") or []:
  ips=c.get("ips") or {}
  print(c.get("id"), "online="+str(c.get("online")), "link="+str(c.get("link")),
        "ip="+str(c.get("ip")), "usb="+str(ips.get("usb")), "wifi="+str(ips.get("wifi")),
        "age="+str(round(float(c.get("age_s") or -1),1)))
'
echo "=== bridge / usb ifaces ==="
ip -br a | grep -E 'br-bhvr|usb|192.168.7' || true
bridge link 2>/dev/null | head -20 || true
echo "=== dnsmasq / dhcp leases ==="
systemctl is-active dnsmasq 2>/dev/null || systemctl is-active bhvr-usb-dhcp 2>/dev/null || true
ls /var/lib/misc/dnsmasq.leases 2>/dev/null && cat /var/lib/misc/dnsmasq.leases || true
ls /var/lib/dnsmasq/*.leases 2>/dev/null; cat /var/lib/dnsmasq/*.leases 2>/dev/null || true
# common bhvr lease paths
find /var/lib -name '*lease*' 2>/dev/null | head -20
grep -rni '192.168.7' /var/lib/misc/ /etc/dnsmasq* 2>/dev/null | head -30 || true
echo "=== lsusb gadgets ==="
lsusb | grep -iE '1d6b|gadget|Composite|Hub' || lsusb
echo "=== mqtt sample 8s ==="
if command -v mosquitto_sub >/dev/null; then
  timeout 8 mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/+/state' -v 2>&1 | head -40 || true
fi
echo "=== ping USB known IPs ==="
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  if ping -c 1 -W 1 "$ip" >/dev/null 2>&1; then
    echo -n "USB_PING_OK $ip "
    ssh "${KEY[@]}" "admin@$ip" 'hostname; cat /sys/class/net/usb0/operstate 2>/dev/null; ip -br a show usb0 2>/dev/null; ip route | head -5' 2>&1 | tr '\n' ' | '
    echo
  else
    echo "USB_PING_FAIL $ip"
  fi
done
echo "=== wifi SSH probe (from last roster wifi if any) ==="
# try common wifi from prior sessions
for ip in 10.248.233.15 10.248.235.74 10.248.238.167 10.248.229.141; do
  if ping -c 1 -W 1 "$ip" >/dev/null 2>&1; then
    echo -n "WIFI_PING_OK $ip "
    ssh "${KEY[@]}" "admin@$ip" 'hostname; ip -br a | grep -E "usb0|wlan0"; systemctl is-active bhvr-cam-usb-gadget.service; systemctl is-active bhvr-cam-announce.timer' 2>&1 | tr '\n' ' | '
    echo
  else
    echo "WIFI_PING_FAIL $ip"
  fi
done
echo DIAG_POST_REBOOT_DONE
