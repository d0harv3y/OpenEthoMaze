#!/bin/bash
# Keep only debs whose package name is in the Inst list (plus keep nothing else).
set -euo pipefail
DEBDIR="${1:-$HOME/bhvr-debs}"
LIST="${2:-/tmp/cam_inst_pkgs.txt}"
KEEP="$DEBDIR/.keep_$$"
mkdir -p "$KEEP"
while read -r p; do
  [[ -z "$p" ]] && continue
  shopt -s nullglob
  for f in "$DEBDIR"/"${p}"_*.deb; do
    mv -n "$f" "$KEEP/"
  done
done < "$LIST"
# drop extras
find "$DEBDIR" -maxdepth 1 -name '*.deb' -delete
mv "$KEEP"/*.deb "$DEBDIR/" 2>/dev/null || true
rmdir "$KEEP" 2>/dev/null || rm -rf "$KEEP"
echo "kept $(ls "$DEBDIR"/*.deb 2>/dev/null | wc -l) debs"
du -sh "$DEBDIR"
