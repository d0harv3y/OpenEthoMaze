#!/bin/bash
# Remount bhvr session SSD (label=random, NTFS) and point kiosk data_root at it.
# Prefer boot automount: sudo bash …/install_ssd_automount.sh (once).
# Usage on NVR: sudo bash ~/deploy/bhvr-nvr/scripts/remount_ssd.sh
set -euo pipefail

LABEL=random
DEV="/dev/disk/by-label/${LABEL}"
MNT=/media/admin/random
BHVR="${MNT}/bhvr"
KIOSK_CFG="${HOME}/bhvr-kiosk/config.yaml"
PATCH="${HOME}/deploy/bhvr-nvr/scripts/patch_kiosk_data_root.py"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "re-run as: sudo bash $0" >&2
  exit 1
fi

# If systemd automount is installed, use it (same force options as below).
if systemctl cat media-admin-random.mount >/dev/null 2>&1; then
  echo "using systemd media-admin-random.mount"
  systemctl start media-admin-random.mount
  systemctl start bhvr-ssd-ready.service 2>/dev/null || \
    /usr/local/sbin/bhvr-ssd-post-mount 2>/dev/null || true
  findmnt "$MNT" || true
  df -h "$MNT" 2>/dev/null || true
  echo "Litmus: curl -sS http://127.0.0.1:8080/api/health | grep data_root"
  exit 0
fi

[[ -e "$DEV" ]] || { echo "missing $DEV"; lsblk; exit 1; }

# Ensure mountpoint exists and admin can traverse /media/admin
install -d -m 0755 /media/admin
# Keep udisks-style path; admin needs rx on parents (already r-x).
install -d -o admin -g admin -m 0755 "$MNT"

if mountpoint -q "$MNT"; then
  echo "already mounted: $MNT"
  findmnt "$MNT"
else
  # Volume was dirty after unclean unplug — ntfs3 needs force; ntfs-3g uses remove_hiberfile/force.
  if grep -qw ntfs3 /proc/filesystems; then
    echo "mounting ntfs3 force → $MNT"
    mount -t ntfs3 -o force,uid=1000,gid=1000,umask=022 "$DEV" "$MNT"
  else
    echo "mounting ntfs-3g force → $MNT"
    mount -t ntfs-3g -o force,uid=1000,gid=1000,umask=022 "$DEV" "$MNT"
  fi
  findmnt "$MNT"
fi

install -d -o admin -g admin -m 0755 "$BHVR"
echo "SSD ready: $BHVR"
df -h "$MNT"

# Flip kiosk data_root as admin (not root-owned config write via sudo -u)
if [[ -f "$PATCH" ]]; then
  sudo -u admin python3 "$PATCH" || true
elif [[ -f "$KIOSK_CFG" ]]; then
  sudo -u admin python3 - <<PY
from pathlib import Path
import re
p = Path("$KIOSK_CFG")
t = p.read_text()
t2 = re.sub(r"^data_root:.*$", "data_root: /media/admin/random/bhvr", t, count=1, flags=re.M)
if "data_root:" not in t2:
    t2 = "data_root: /media/admin/random/bhvr\n" + t2
p.write_text(t2)
print("data_root → /media/admin/random/bhvr")
PY
fi

echo "Litmus: curl -sS http://127.0.0.1:8080/api/health | grep data_root"
echo "  (restart kiosk if health still shows /data/bhvr)"
echo "Tip: install boot automount once → sudo bash $(dirname "$0")/install_ssd_automount.sh"
