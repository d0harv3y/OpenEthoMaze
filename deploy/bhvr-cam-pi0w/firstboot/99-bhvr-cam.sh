#!/bin/bash
# Firstboot for bhvr-cam — offline / air-gap safe (no network apt).
# Installs listen + MQTT announce + record units. Optional: dpkg local debs/.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TREE="$(cd "$SCRIPT_DIR/.." && pwd)"

mkdir -p /data/bhvr/current /var/lib/bhvr /run/bhvr
chmod 755 /data/bhvr /var/lib/bhvr

# Firstrun (systemd.run) can race Imager cloud-init — wait for the admin user.
wait_for_admin_user() {
  local t=0 max_sec="${1:-120}"
  while ((t < max_sec)); do
    if id -u admin >/dev/null 2>&1 && [[ -d /home/admin ]]; then
      echo "admin user ready after ${t}s"
      return 0
    fi
    echo "waiting for cloud-init admin user… t=${t}s"
    sleep 5
    t=$((t + 5))
  done
  echo "ERROR: admin user not present after ${max_sec}s (Imager user=admin required)" >&2
  return 1
}
wait_for_admin_user 120

# NVR BatchMode SSH (focus live / science record). Imager may have missed this.
install_nvr_authorized_keys() {
  local keys="$TREE/ssh/nvr_authorized_keys"
  local auth="/home/admin/.ssh/authorized_keys"
  [[ -f "$keys" ]] || {
    echo "NOTE: no $keys — NVR SSH trust not baked (focus/record will fail)" >&2
    return 0
  }
  install -d -m 0700 -o admin -g admin /home/admin/.ssh
  touch "$auth"
  chown admin:admin "$auth"
  chmod 0600 "$auth"
  local line added=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    if ! grep -qxF "$line" "$auth" 2>/dev/null; then
      printf '%s\n' "$line" >>"$auth"
      added=$((added + 1))
    fi
  done <"$keys"
  chown admin:admin "$auth"
  echo "nvr authorized_keys: merged (+$added new) → $auth"
}
install_nvr_authorized_keys

# Best-effort local packages (rpicam-apps etc.) — see offline/README.md
if compgen -G "$TREE/debs/*.deb" >/dev/null; then
  echo "installing local debs from $TREE/debs ..."
  dpkg -i "$TREE/debs"/*.deb || true
fi

install -m 0755 "$TREE/scripts/record_h264.sh" /usr/local/bin/bhvr-cam-record
install -m 0755 "$TREE/scripts/announce_mqtt.py" /usr/local/bin/bhvr-cam-announce
install -m 0755 "$TREE/scripts/find_broker.py" /usr/local/bin/bhvr-cam-find-broker
install -m 0755 "$TREE/scripts/clean_broker_override.sh" /usr/local/bin/bhvr-cam-clean-broker-override
# HTU21D reader (imported by announce); also CLI litmus.
install -d -m 0755 /usr/local/lib/bhvr
install -m 0755 "$TREE/scripts/htu21d.py" /usr/local/lib/bhvr/htu21d.py
install -m 0755 "$TREE/scripts/htu21d.py" /usr/local/bin/bhvr-cam-htu21d
if [[ -f "$TREE/scripts/announce_mqtt.sh" ]]; then
  install -m 0755 "$TREE/scripts/announce_mqtt.sh" /usr/local/bin/bhvr-cam-announce.sh
fi
# I2C for HTU21D breakout (reboot may be required if just enabled).
# dtparam alone loads i2c_bcm2835; i2c-dev creates /dev/i2c-*.
echo i2c-dev >/etc/modules-load.d/i2c-dev.conf
if [[ -f "$TREE/scripts/_ensure_i2c_arm.py" ]]; then
  python3 "$TREE/scripts/_ensure_i2c_arm.py" || echo "WARN: i2c_arm enable failed (non-fatal)" >&2
fi
install -m 0644 "$TREE/systemd/bhvr-cam-announce.service" /etc/systemd/system/
install -m 0644 "$TREE/systemd/bhvr-cam-announce.timer" /etc/systemd/system/
install -m 0644 "$TREE/systemd/bhvr-cam-htu-sample.service" /etc/systemd/system/
install -m 0644 "$TREE/systemd/bhvr-cam-htu-sample.timer" /etc/systemd/system/
install -m 0644 "$TREE/systemd/bhvr-cam-broker-listen.service" /etc/systemd/system/
install -m 0644 "$TREE/systemd/bhvr-cam-record.service" /etc/systemd/system/

# USB gadget CDC ECM (wired tether to NVR) — needs reboot if dtoverlay=dwc2 was just added.
if [[ -x "$TREE/scripts/install_usb_gadget.sh" ]]; then
  bash "$TREE/scripts/install_usb_gadget.sh" || echo "WARN: USB gadget install failed (non-fatal)" >&2
fi

if [[ ! -f /etc/bhvr-cam.env ]]; then
  cat >/etc/bhvr-cam.env <<'EOF'
# Optional override only — leave MQTT_BROKER unset to use UDP beacon from NVR.
# MQTT_BROKER=10.0.0.1
MQTT_PORT=1883
MQTT_TOPIC_PREFIX=bhvr/cam
PROFILE=720p
EOF
  chmod 0644 /etc/bhvr-cam.env
fi

systemctl daemon-reload
systemctl enable --now bhvr-cam-broker-listen.service
systemctl enable --now bhvr-cam-htu-sample.timer
systemctl enable --now bhvr-cam-announce.timer
# record is started on demand by NVR kiosk — do not enable at boot
systemctl disable bhvr-cam-record.service 2>/dev/null || true

# mDNS not used for MQTT roster; avahi often burns 25–70% CPU on Zero during encode.
systemctl disable --now avahi-daemon.service avahi-daemon.socket 2>/dev/null \
  || systemctl disable --now avahi-daemon 2>/dev/null \
  || true

# Passwordless sudo for kiosk SSH control + maintenance apt (closed lab appliance)
cat >/etc/sudoers.d/bhvr-cam <<'EOF'
# bhvr-cam — NVR session start/stop without interactive sudo
admin ALL=(ALL) NOPASSWD: /bin/systemctl, /usr/bin/systemctl, /usr/bin/tee, /bin/mkdir, /usr/bin/mkdir
admin ALL=(ALL) NOPASSWD: /bin/chmod, /usr/bin/chmod, /bin/cp, /usr/bin/cp
# Online/offline package install (install_runtime_pkgs.sh / dpkg local debs)
admin ALL=(ALL) NOPASSWD: /usr/bin/apt-get, /usr/bin/apt, /usr/bin/dpkg
EOF
chmod 440 /etc/sudoers.d/bhvr-cam
echo "bhvr-cam slim firstboot done (no network apt)."
echo "  listen: bhvr-cam-broker-listen.service"
echo "  announce: bhvr-cam-announce.timer (stdlib MQTT)"
echo "  usb gadget: bhvr-cam-usb-gadget.service (CDC ECM → NVR; reboot if dwc2 just added)"
echo "  avahi-daemon: disabled (CPU hygiene; roster uses MQTT/USB)"
echo "  ssh: NVR pubkey → /home/admin/.ssh/authorized_keys (if ssh/nvr_authorized_keys present)"
echo "  record: bhvr-cam-record.service (needs rpicam-vid)"
echo "  live mpegts/UDP: needs ffmpeg in debs/ or install_runtime_pkgs.sh (not on WSU-IoT)"
command -v python3 >/dev/null || echo "WARN: python3 missing" >&2
command -v rpicam-vid >/dev/null || echo "NOTE: rpicam-vid not installed yet — bake debs/ (offline/README.md)"
command -v ffmpeg >/dev/null || echo "NOTE: ffmpeg missing — kiosk mpegts preview needs it; bake debs/ (offline/README.md)"
ip -br a || true
cat /sys/class/net/wlan0/address 2>/dev/null || true
