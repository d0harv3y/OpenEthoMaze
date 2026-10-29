#!/bin/bash
# Install systemd mount so LABEL=random SSD remounts on boot (no manual remount_ssd).
# Run on NVR: sudo bash ~/deploy/bhvr-nvr/scripts/install_ssd_automount.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "re-run as: sudo bash $0" >&2
  exit 1
fi

HERE="$(cd "$(dirname "$0")" && pwd)"
UNIT_SRC="$(cd "$HERE/.." && pwd)/systemd"
MOUNT_SRC="${UNIT_SRC}/media-admin-random.mount"
READY_SRC="${UNIT_SRC}/bhvr-ssd-ready.service"
POST_SRC="${HERE}/ssd_post_mount.sh"

[[ -f "$MOUNT_SRC" ]] || { echo "missing $MOUNT_SRC" >&2; exit 1; }
[[ -f "$READY_SRC" ]] || { echo "missing $READY_SRC" >&2; exit 1; }
[[ -f "$POST_SRC" ]] || { echo "missing $POST_SRC" >&2; exit 1; }

install -d -m 0755 /media/admin
install -d -o admin -g admin -m 0755 /media/admin/random
install -m 0755 "$POST_SRC" /usr/local/sbin/bhvr-ssd-post-mount

# Prefer ntfs3; fall back to ntfs-3g if kernel has no ntfs3.
MOUNT_DST=/etc/systemd/system/media-admin-random.mount
cp "$MOUNT_SRC" "$MOUNT_DST"
if ! grep -qw ntfs3 /proc/filesystems; then
  echo "kernel has no ntfs3 — using ntfs-3g in mount unit"
  sed -i 's/^Type=ntfs3$/Type=ntfs-3g/' "$MOUNT_DST"
fi

install -m 0644 "$READY_SRC" /etc/systemd/system/bhvr-ssd-ready.service

systemctl daemon-reload
systemctl enable media-admin-random.mount bhvr-ssd-ready.service
# Mount first; ready oneshot has a timeout so install never hangs on kiosk restart.
systemctl start media-admin-random.mount
systemctl start --no-block bhvr-ssd-ready.service
# Wait briefly for mount + post-mount, but do not block forever.
for _ in $(seq 1 30); do
  if systemctl is-active --quiet media-admin-random.mount \
     && { systemctl is-active --quiet bhvr-ssd-ready.service || systemctl is-failed --quiet bhvr-ssd-ready.service; }; then
    break
  fi
  # activating → still starting
  sleep 0.5
done

echo "=== status ==="
systemctl --no-pager --full status media-admin-random.mount bhvr-ssd-ready.service | head -40
findmnt /media/admin/random || true
df -h /media/admin/random 2>/dev/null || true
echo
echo "Boot will remount LABEL=random automatically."
echo "Manual: sudo systemctl restart media-admin-random.mount && sudo systemctl start bhvr-ssd-ready.service"
echo "Legacy:  sudo bash $HERE/remount_ssd.sh"
