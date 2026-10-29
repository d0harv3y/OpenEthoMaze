#!/bin/bash
# From NVR: push networkd DHCP client + announce gateway broker to a tethered cam.
# No static IPs — cam gets 192.168.7.x via DHCP; MQTT broker = DHCP router.
#
# Usage (cam reachable on usb0 link-local or after first lease):
#   bash ~/deploy/bhvr-nvr/scripts/push_cam_usb0_dhcp.sh
#   bash ~/deploy/bhvr-nvr/scripts/push_cam_usb0_dhcp.sh admin@fe80::27:ebff:fe96:f5bb%usb0
#   bash ~/deploy/bhvr-nvr/scripts/push_cam_usb0_dhcp.sh admin@192.168.7.10
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NVR_TREE="$(cd "$SCRIPT_DIR/.." && pwd)"
# Prefer sibling checkout; fall back to staged /tmp from laptop scp.
CAM_TREE="${BHVR_CAM_TREE:-}"
if [[ -z "$CAM_TREE" ]]; then
  for candidate in \
    "$NVR_TREE/../bhvr-cam" \
    "$HOME/bhvr-cam" \
    /tmp/bhvr-cam-dhcp
  do
    if [[ -f "$candidate/scripts/install_usb_gadget.sh" ]] \
      || [[ -f "$candidate/install_usb_gadget.sh" ]]; then
      CAM_TREE="$candidate"
      break
    fi
  done
fi
if [[ -z "${CAM_TREE:-}" ]]; then
  echo "no bhvr-cam tree — scp deploy/bhvr-cam to /tmp/bhvr-cam-dhcp first" >&2
  exit 1
fi

# Normalize layout: /tmp/bhvr-cam-dhcp may already be scripts/network/...
if [[ -f "$CAM_TREE/install_usb_gadget.sh" ]]; then
  # flat scripts dir only — wrap
  :
fi

TARGET="${1:-admin@fe80::27:ebff:fe96:f5bb%usb0}"
SSH=(ssh -o StrictHostKeyChecking=accept-new)
if [[ -f "$HOME/.ssh/id_ed25519_bhvr" ]]; then
  SSH+=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes)
fi

# scp treats ':' as host/path split — breaks fe80::… . Prefer tar|ssh.
# If you must scp: admin@[fe80::…%usb0]:~/path
echo "target=$TARGET tree=$CAM_TREE"

STAGE=$(mktemp -d /tmp/bhvr-cam-push.XXXXXX)
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE"/{scripts,network,systemd,udev}

# Resolve file paths for either full tree or /tmp/bhvr-cam-dhcp layout
pick() {
  local rel="$1"
  if [[ -f "$CAM_TREE/$rel" ]]; then
    echo "$CAM_TREE/$rel"
  elif [[ -f "$CAM_TREE/scripts/$(basename "$rel")" && "$rel" == scripts/* ]]; then
    echo "$CAM_TREE/scripts/$(basename "$rel")"
  else
    echo "$CAM_TREE/$rel"
  fi
}

for rel in \
  scripts/install_usb_gadget.sh \
  scripts/usb_gadget_ecm.sh \
  scripts/announce_mqtt.py \
  network/bhvr-usb0.network \
  systemd/bhvr-cam-usb-gadget.service \
  systemd/bhvr-cam-usb0-dhcp.service \
  udev/99-bhvr-usb0-dhcp.rules
do
  f="$(pick "$rel")"
  [[ -f "$f" ]] || { echo "missing $rel (looked for $f)" >&2; exit 1; }
  sed 's/\r$//' "$f" >"$STAGE/$rel"
done
chmod +x "$STAGE"/scripts/*

# Pipe steals stdin → sudo cannot prompt. Push first, then ssh -t for install.
tar -C "$STAGE" -czf - . | "${SSH[@]}" "$TARGET" \
  'mkdir -p ~/bhvr-cam && tar -C ~/bhvr-cam -xzf - && chmod +x ~/bhvr-cam/scripts/*'
echo "files on cam; sudo install next (cam sudo password if asked)…"
"${SSH[@]}" -t "$TARGET" 'sudo bash ~/bhvr-cam/scripts/install_usb_gadget.sh'
echo "=== cam addresses ==="
"${SSH[@]}" "$TARGET" 'ip -br a; echo ---; ip -4 route; echo ---; networkctl status usb0 2>/dev/null | head -30 || true'
echo "=== NVR leases ==="
networkctl status usb0 2>/dev/null | grep -E 'Offered|Address' || true
echo "done — expect cam 192.168.7.x and MQTT via gateway (no static MQTT_BROKER)"
