#!/bin/bash
# NVR host side for N× cam USB gadget CDC ECM.
#
# Each Zero creates its own netdev (usb0, usb1, …). Those are bridged into
# br-bhvr with a single 192.168.7.1/24 + DHCPServer so every cam shares one
# subnet and uses the bridge address as MQTT gateway.
#
# No Windows-style driver: kernel cdc_ether/usbnet are enough.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TREE="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root: sudo bash $0" >&2
  exit 1
fi

install -d /etc/systemd/network

# Drop legacy single-iface address-on-usb0 unit if present.
rm -f /etc/systemd/network/bhvr-usb-gadget.network

install -m 0644 "$TREE/systemd/bhvr-usb-br.netdev" \
  /etc/systemd/network/bhvr-usb-br.netdev
install -m 0644 "$TREE/systemd/bhvr-usb-br.network" \
  /etc/systemd/network/bhvr-usb-br.network
install -m 0644 "$TREE/systemd/bhvr-usb-gadget-slave.network" \
  /etc/systemd/network/bhvr-usb-gadget-slave.network

# Leave gadget NICs to networkd (NM keeps wlan0).
install -d /etc/NetworkManager/conf.d
cat >/etc/NetworkManager/conf.d/99-bhvr-unmanaged-usb.conf <<'EOF'
[keyfile]
unmanaged-devices=driver:cdc_ether;driver:rndis_host;interface-name:br-bhvr
EOF
systemctl reload NetworkManager 2>/dev/null || true

modprobe usbnet 2>/dev/null || true
modprobe cdc_ether 2>/dev/null || true
modprobe bridge 2>/dev/null || true

install -m 0644 "$TREE/udev/99-bhvr-usb-gadget.rules" \
  /etc/udev/rules.d/99-bhvr-usb-gadget.rules
udevadm control --reload-rules 2>/dev/null || true

systemctl enable systemd-networkd.service
systemctl restart systemd-networkd.service

echo "bhvr-nvr multi-cam USB gadget host ready."
echo "  Bridge:  br-bhvr @ 192.168.7.1/24"
echo "  Slaves:  every cdc_ether / rndis_host (usb0, usb1, …)"
echo "  DHCP:    192.168.7.10–192.168.7.50"
echo "Litmus:"
echo "  lsusb | grep 1d6b:0104"
echo "  ip -br a | grep -E 'br-bhvr|usb'"
echo "  networkctl"
echo "  # expect N cams with 192.168.7.x and MQTT via 192.168.7.1"
ip -br a || true
networkctl 2>/dev/null || true
