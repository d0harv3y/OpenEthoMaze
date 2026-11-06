#!/bin/bash
# One-shot on NVR: merge ~/bhvr-nvr into ~/deploy/bhvr-nvr, then remove ~/bhvr-nvr.
# No symlink. Run as admin (no sudo required for home dirs).
set -euo pipefail
OLD="${HOME}/bhvr-nvr"
NEW="${HOME}/deploy/bhvr-nvr"

[[ -d "$NEW" ]] || { echo "missing $NEW" >&2; exit 1; }

if [[ ! -d "$OLD" ]]; then
  echo "nothing to collapse ($OLD absent)"
  exit 0
fi

if [[ "$OLD" -ef "$NEW" ]]; then
  echo "already same inode — refuse"
  exit 1
fi

echo "merging $OLD → $NEW"
mkdir -p "$NEW/scripts" "$NEW/systemd" "$NEW/mediamtx" "$NEW/udev"
# Copy files that exist only in OLD (do not overwrite newer NEW copies).
rsync -a --ignore-existing "$OLD/" "$NEW/"
# Always keep mediamtx.yml from OLD if NEW lacks it
if [[ -f "$OLD/mediamtx/mediamtx.yml" && ! -f "$NEW/mediamtx/mediamtx.yml" ]]; then
  cp -a "$OLD/mediamtx/mediamtx.yml" "$NEW/mediamtx/mediamtx.yml"
fi

echo "removing $OLD"
rm -rf "$OLD"

echo "done. canonical=$NEW"
ls -ld "$NEW"
test ! -e "$OLD"
echo "OK collapsed"
