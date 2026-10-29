#!/bin/bash
# After media-admin-random.mount: ensure bhvr/ and point kiosk data_root at SSD.
# Installed to /usr/local/sbin/bhvr-ssd-post-mount by install_ssd_automount.sh.
set -euo pipefail

MNT=/media/admin/random
BHVR="${MNT}/bhvr"
KIOSK_CFG=/home/admin/bhvr-kiosk/config.yaml
PATCH=/home/admin/deploy/bhvr-nvr/scripts/patch_kiosk_data_root.py

if ! mountpoint -q "$MNT"; then
  echo "ssd_post_mount: $MNT not mounted" >&2
  exit 1
fi

install -d -o admin -g admin -m 0755 "$BHVR"
echo "SSD ready: $BHVR"
df -h "$MNT"

if [[ -f "$PATCH" ]]; then
  sudo -u admin python3 "$PATCH" || true
elif [[ -f "$KIOSK_CFG" ]]; then
  sudo -u admin python3 - <<'PY'
from pathlib import Path
import re
p = Path("/home/admin/bhvr-kiosk/config.yaml")
t = p.read_text()
t2 = re.sub(r"^data_root:.*$", "data_root: /media/admin/random/bhvr", t, count=1, flags=re.M)
if "data_root:" not in t2:
    t2 = "data_root: /media/admin/random/bhvr\n" + t2
p.write_text(t2)
print("data_root → /media/admin/random/bhvr")
PY
fi

# Do not block on kiosk restart (systemctl start of this oneshot can deadlock /
# hang for minutes under load). Operator or a separate --no-block is enough.
if systemctl is-enabled --quiet bhvr-kiosk-web.service 2>/dev/null; then
  systemctl --no-block try-restart bhvr-kiosk-web.service >/dev/null 2>&1 || true
  echo "kiosk restart requested (--no-block); check: systemctl is-active bhvr-kiosk-web"
fi
