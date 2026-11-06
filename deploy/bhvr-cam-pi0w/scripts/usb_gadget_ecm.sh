#!/bin/bash
# Bring up USB gadget CDC ECM (usb0) so a Pi Zero W enumerates as ethernet on the NVR.
# Prefer CDC ECM over classic g_ether/RNDIS — Linux hosts need no extra driver.
#
# Usage: bhvr-cam-usb-gadget [start|stop]
set -euo pipefail

ACTION="${1:-start}"
GADGET_NAME=bhvr
CONFIGFS=/sys/kernel/config/usb_gadget
GADGET="$CONFIGFS/$GADGET_NAME"

_serial() {
  tr -d '\0' </proc/device-tree/serial-number 2>/dev/null \
    || cat /sys/firmware/devicetree/base/serial-number 2>/dev/null | tr -d '\0' \
    || echo "0000000000000000"
}

# Stable locally-administered MACs derived from board serial (unique per Zero).
_macs_from_serial() {
  local s h
  s="$(_serial)"
  h="$(printf '%s' "$s" | sha256sum | awk '{print $1}')"
  # host (NVR-facing) and device (cam usb0) — unicast, locally administered (x2 bit set)
  DEV_MAC=$(printf '02:27:eb:%s:%s:%s' "${h:0:2}" "${h:2:2}" "${h:4:2}")
  HOST_MAC=$(printf '02:27:ec:%s:%s:%s' "${h:6:2}" "${h:8:2}" "${h:10:2}")
}

stop_gadget() {
  if [[ ! -d "$GADGET" ]]; then
    return 0
  fi
  if [[ -e "$GADGET/UDC" ]]; then
    echo "" >"$GADGET/UDC" 2>/dev/null || true
  fi
  rm -f "$GADGET/configs/c.1/ecm.usb0" 2>/dev/null || true
  rmdir "$GADGET/configs/c.1/strings/0x409" 2>/dev/null || true
  rmdir "$GADGET/configs/c.1" 2>/dev/null || true
  rmdir "$GADGET/functions/ecm.usb0" 2>/dev/null || true
  rmdir "$GADGET/strings/0x409" 2>/dev/null || true
  rmdir "$GADGET" 2>/dev/null || true
  echo "bhvr-cam-usb-gadget: stopped"
}

start_gadget() {
  if [[ -d /sys/class/net/usb0 ]]; then
    echo "bhvr-cam-usb-gadget: usb0 already present"
    return 0
  fi

  modprobe dwc2 2>/dev/null || true
  modprobe libcomposite

  if [[ ! -d "$CONFIGFS" ]]; then
    mount -t configfs none /sys/kernel/config 2>/dev/null || true
  fi
  if [[ ! -d "$CONFIGFS" ]]; then
    echo "bhvr-cam-usb-gadget: configfs missing" >&2
    exit 1
  fi

  stop_gadget
  _macs_from_serial

  mkdir -p "$GADGET"
  echo "0x1d6b" >"$GADGET/idVendor"   # Linux Foundation
  echo "0x0104" >"$GADGET/idProduct"  # Multifunction Composite Gadget
  echo "0x0100" >"$GADGET/bcdDevice"
  echo "0x0200" >"$GADGET/bcdUSB"

  mkdir -p "$GADGET/strings/0x409"
  echo "$(_serial)" >"$GADGET/strings/0x409/serialnumber"
  echo "OpenEthoMaze" >"$GADGET/strings/0x409/manufacturer"
  echo "bhvr-cam CDC ECM" >"$GADGET/strings/0x409/product"

  mkdir -p "$GADGET/configs/c.1/strings/0x409"
  echo "ECM" >"$GADGET/configs/c.1/strings/0x409/configuration"
  echo 250 >"$GADGET/configs/c.1/MaxPower"

  mkdir -p "$GADGET/functions/ecm.usb0"
  echo "$DEV_MAC" >"$GADGET/functions/ecm.usb0/dev_addr"
  echo "$HOST_MAC" >"$GADGET/functions/ecm.usb0/host_addr"

  ln -sf "$GADGET/functions/ecm.usb0" "$GADGET/configs/c.1/"

  local udc
  udc="$(ls -1 /sys/class/udc 2>/dev/null | head -1 || true)"
  if [[ -z "$udc" ]]; then
    echo "bhvr-cam-usb-gadget: no UDC (is dtoverlay=dwc2 active? data micro-USB plugged?)" >&2
    exit 1
  fi
  echo "$udc" >"$GADGET/UDC"
  # CDC ECM: host stays NO-CARRIER until the device netdev is administratively up.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if [[ -d /sys/class/net/usb0 ]]; then
      ip link set usb0 up || true
      break
    fi
    sleep 0.3
  done
  echo "bhvr-cam-usb-gadget: started UDC=$udc usb0 dev=$DEV_MAC host=$HOST_MAC state=$(cat /sys/class/net/usb0/operstate 2>/dev/null || echo missing)"
}

case "$ACTION" in
  start) start_gadget ;;
  stop) stop_gadget ;;
  *)
    echo "usage: $0 [start|stop]" >&2
    exit 2
    ;;
esac
