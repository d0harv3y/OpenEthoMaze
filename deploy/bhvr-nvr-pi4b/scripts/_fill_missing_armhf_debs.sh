#!/bin/bash
# Download only packages listed in MISSING file (one name per line, no MISSING: prefix).
set -euo pipefail
OUT="${1:-$HOME/bhvr-debs}"
MISSING_FILE="${2:-/tmp/cam_missing_pkgs.txt}"
IDX="${TMPDIR:-/tmp}/bhvr-armhf-fill-$$"
mkdir -p "$OUT" "$IDX"
cd "$IDX"

curl -fsSL -o rpi.gz http://archive.raspberrypi.com/debian/dists/trixie/main/binary-armhf/Packages.gz
curl -fsSL -o deb.gz http://deb.debian.org/debian/dists/trixie/main/binary-armhf/Packages.gz
curl -fsSL -o rasp.gz http://raspbian.raspberrypi.com/raspbian/dists/trixie/main/binary-armhf/Packages.gz
gunzip -kf rpi.gz deb.gz rasp.gz
cat rpi deb rasp > ALL.Packages

lookup_filename() {
  local pkg="$1"
  awk -v pkg="$pkg" '
    BEGIN { RS=""; FS="\n" }
    {
      name=""; fn=""
      for (i=1;i<=NF;i++) {
        if ($i ~ /^Package: /) name=substr($i,10)
        if ($i ~ /^Filename: /) fn=substr($i,11)
      }
      if (name==pkg) { print fn; exit }
    }
  ' ALL.Packages
}

ok=0
fail=0
while read -r pkg; do
  [[ -z "$pkg" ]] && continue
  pkg="${pkg#MISSING:}"
  if ls "$OUT"/"${pkg}"_*.deb >/dev/null 2>&1; then
    echo "have: $pkg"
    continue
  fi
  if apt-cache show "${pkg}:armhf" >/dev/null 2>&1 || apt-cache show "$pkg" >/dev/null 2>&1; then
    if (cd "$OUT" && apt-get download "${pkg}:armhf" >/dev/null 2>&1) \
      || (cd "$OUT" && apt-get download "$pkg" >/dev/null 2>&1); then
      echo "apt: $pkg"
      ok=$((ok + 1))
      continue
    fi
  fi
  fn="$(lookup_filename "$pkg")"
  if [[ -z "$fn" ]]; then
    echo "FAIL no-index: $pkg" >&2
    fail=$((fail + 1))
    continue
  fi
  dest="$(basename "$fn")"
  got=0
  for base in \
    http://archive.raspberrypi.com/debian \
    http://raspbian.raspberrypi.com/raspbian \
    http://deb.debian.org/debian
  do
    if curl -fsSL -o "$OUT/$dest.part" "$base/$fn"; then
      mv "$OUT/$dest.part" "$OUT/$dest"
      echo "curl: $pkg"
      ok=$((ok + 1))
      got=1
      break
    fi
    rm -f "$OUT/$dest.part"
  done
  if [[ "$got" -eq 0 ]]; then
    echo "FAIL curl: $pkg ($fn)" >&2
    fail=$((fail + 1))
  fi
done < "$MISSING_FILE"

echo "filled ok=$ok fail=$fail"
du -sh "$OUT"
rm -rf "$IDX"
