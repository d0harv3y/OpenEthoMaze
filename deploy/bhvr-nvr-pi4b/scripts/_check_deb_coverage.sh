#!/bin/bash
set -euo pipefail
DEBDIR="${1:-$HOME/bhvr-debs}"
LIST="${2:-/tmp/cam_inst_pkgs.txt}"
missing=0
while read -r p; do
  [[ -z "$p" ]] && continue
  if ! ls "$DEBDIR"/"${p}"_*.deb >/dev/null 2>&1; then
    echo "MISSING:$p"
    missing=$((missing + 1))
  fi
done < "$LIST"
echo "missing_count=$missing"
du -sh "$DEBDIR"
ls "$DEBDIR"/*.deb | wc -l
