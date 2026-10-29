#!/bin/bash
# Install CDC ECM USB gadget on bhvr-cam (Pi Zero W). Idempotent.
# Requires: data micro-USB to NVR (or powered hub), dtoverlay=dwc2, reboot once if overlay was missing.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TREE="$(cd "$SCRIPT_DIR/.." && pwd)"

ensure_dwc2_overlay() {
  # Stock Pi OS parks otg_mode under [cm4] and dwc2 under [cm5]. Those filters
  # do not match Pi Zero W — in-place sed then looks "done" while UDC stays empty
  # and dwc_otg owns the bus as host. Always put peripheral under [all].
  local f py
  for f in /boot/firmware/config.txt /boot/config.txt; do
    [[ -f "$f" ]] || continue
    py="$(dirname "$0")/../scripts/_ensure_dwc2_peripheral.py"
    if [[ ! -f "$py" ]]; then
      py="/usr/local/lib/bhvr/_ensure_dwc2_peripheral.py"
    fi
    if [[ -f "$py" ]]; then
      python3 "$py" "$f"
      return 0
    fi
    # Inline fallback (same rules as _ensure_dwc2_peripheral.py)
    python3 - "$f" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines(keepends=True)
out, section, have = [], "", False
for line in lines:
    s = line.strip()
    if s.startswith("[") and s.endswith("]"):
        section = s[1:-1].strip().lower()
        out.append(line)
        continue
    if s.startswith("otg_mode=1"):
        out.append("# bhvr: otg_mode=1 breaks Pi Zero dwc2 UDC\n#otg_mode=1\n")
        continue
    if s.startswith("dtoverlay=dwc2"):
        if section in ("", "all"):
            continue
        out.append(f"# bhvr: moved dwc2 to all-section (was under [{section}])\n")
        continue
    if s == "# bhvr-cam USB gadget (CDC ECM toward NVR)":
        continue
    out.append(line)
text = "".join(out)
needle = "# bhvr-cam USB gadget (CDC ECM toward NVR)\ndtoverlay=dwc2,dr_mode=peripheral\n"
if "dtoverlay=dwc2,dr_mode=peripheral" not in text:
    # Section header only — comments may contain the substring "[all]".
    idx = text.find("\n[all]")
    if text.startswith("[all]"):
        text = "[all]\n" + needle + text[len("[all]"):].lstrip("\n")
    elif idx >= 0:
        text = text[: idx + 1] + "[all]\n" + needle + text[idx + 1 + len("[all]"):].lstrip("\n")
    else:
        text = text.rstrip() + "\n\n[all]\n" + needle
path.write_text(text, encoding="utf-8")
print(f"ensured dwc2 peripheral under [all] in {path}")
PY
    return 0
  done
  echo "WARN: no config.txt found — add dtoverlay=dwc2,dr_mode=peripheral under [all]" >&2
}

install -m 0755 "$TREE/scripts/usb_gadget_ecm.sh" /usr/local/bin/bhvr-cam-usb-gadget
install -m 0644 "$TREE/systemd/bhvr-cam-usb-gadget.service" /etc/systemd/system/
install -m 0644 "$TREE/systemd/bhvr-cam-usb0-dhcp.service" /etc/systemd/system/
install -m 0755 "$TREE/scripts/announce_mqtt.py" /usr/local/bin/bhvr-cam-announce

ensure_dwc2_overlay

# usb0 = systemd-networkd DHCP client (no static IPs). Leave wlan0 to NM.
install -d /etc/systemd/network
install -m 0644 "$TREE/network/bhvr-usb0.network" /etc/systemd/network/bhvr-usb0.network
install -d /etc/udev/rules.d
install -m 0644 "$TREE/udev/99-bhvr-usb0-dhcp.rules" /etc/udev/rules.d/99-bhvr-usb0-dhcp.rules
udevadm control --reload-rules 2>/dev/null || true

install -d /etc/NetworkManager/conf.d
cat >/etc/NetworkManager/conf.d/99-bhvr-unmanaged-usb0.conf <<'EOF'
[keyfile]
unmanaged-devices=interface-name:usb0
EOF
# Drop legacy NM keyfile if present (would fight networkd).
rm -f /etc/NetworkManager/system-connections/bhvr-usb0.nmconnection
systemctl reload NetworkManager 2>/dev/null || true

# Enable networkd for usb0 DHCP only. Do not restart it here — a live tether
# restart / wait-online can hang the install SSH session.
systemctl enable systemd-networkd.service
systemctl start systemd-networkd.service 2>/dev/null || true
# wait-online wants "all managed links up"; usb0 alone must not block boot.
systemctl disable systemd-networkd-wait-online.service 2>/dev/null || true

if [[ -f /etc/bhvr-cam.env ]] && ! grep -q '^# BHVR_USB_GADGET' /etc/bhvr-cam.env; then
  cat >>/etc/bhvr-cam.env <<'EOF'

# BHVR_USB_GADGET — wired tether (CDC ECM). Broker = DHCP router on usb0
# (NVR 192.168.7.1) via announce_mqtt — no static MQTT_BROKER required.
EOF
fi

systemctl daemon-reload
systemctl enable bhvr-cam-usb-gadget.service
systemctl enable bhvr-cam-usb0-dhcp.service

if [[ -d /sys/class/udc ]] && [[ -n "$(ls -A /sys/class/udc 2>/dev/null || true)" ]]; then
  # Prefer start over restart — tearing down ECM mid-SSH drops this session.
  if systemctl is-active --quiet bhvr-cam-usb-gadget.service; then
    echo "gadget already active; leave UDC bound."
  else
    systemctl start bhvr-cam-usb-gadget.service
  fi
  # DHCP refresh is best-effort; networkctl can block if no lease yet.
  timeout 15 systemctl start bhvr-cam-usb0-dhcp.service \
    || echo "WARN: usb0 DHCP refresh timed out (lease may still arrive)" >&2
  echo "gadget started (UDC present)."
else
  echo "dtoverlay=dwc2 may need a reboot before UDC appears. Reboot, then:"
  echo "  sudo systemctl start bhvr-cam-usb-gadget bhvr-cam-usb0-dhcp"
fi

echo "bhvr-cam USB gadget install done (DHCP on usb0, no static IPs)."
ip -br link | grep -E 'usb0|wlan0' || true
ip -4 -br a show usb0 2>/dev/null || true
