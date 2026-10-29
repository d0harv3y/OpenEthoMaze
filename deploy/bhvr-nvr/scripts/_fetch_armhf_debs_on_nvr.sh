#!/bin/bash
# Fetch armhf ffmpeg + rpicam-apps (+ recursive Depends) on an online arm64 NVR.
# No sudo: uses apt-get download where indexed, else curl from Packages.gz.
# Usage: bash _fetch_armhf_debs_on_nvr.sh [OUT_DIR]
set -euo pipefail

OUT="${1:-$HOME/bhvr-debs}"
IDX="${TMPDIR:-/tmp}/bhvr-armhf-idx-$$"
SEED=(ffmpeg rpicam-apps)

mkdir -p "$OUT" "$IDX"
cd "$IDX"

fetch_index() {
  local name="$1" url="$2"
  echo "index: $name"
  curl -fsSL -o "${name}.gz" "$url"
  gunzip -kf "${name}.gz"
}

# Raspberry Pi archive (ffmpeg + rpicam-apps) + Debian/Raspbian for transitive libs
fetch_index rpi http://archive.raspberrypi.com/debian/dists/trixie/main/binary-armhf/Packages.gz
fetch_index deb http://deb.debian.org/debian/dists/trixie/main/binary-armhf/Packages.gz
fetch_index rasp http://raspbian.raspberrypi.com/raspbian/dists/trixie/main/binary-armhf/Packages.gz
# security often needed for ffmpeg transitive
fetch_index debsec http://deb.debian.org/debian-security/dists/trixie-security/main/binary-armhf/Packages.gz || true

# Merge indexes (later files override earlier for same Package — prefer rpi first by scanning order)
cat rpi deb rasp debsec 2>/dev/null > ALL.Packages || cat rpi deb rasp > ALL.Packages

lookup_field() {
  # lookup_field <pkg> <Field>
  local pkg="$1" field="$2"
  awk -v pkg="$pkg" -v field="$field" '
    BEGIN { RS=""; FS="\n" }
    {
      name=""; val=""
      for (i=1;i<=NF;i++) {
        if ($i ~ /^Package: /) name=substr($i,10)
        if ($i ~ ("^" field ": ")) val=substr($i, length(field)+3)
      }
      if (name==pkg) { print val; exit }
    }
  ' ALL.Packages
}

lookup_filename() { lookup_field "$1" Filename; }
lookup_depends() {
  local d
  d="$(lookup_field "$1" Depends)"
  local pd
  pd="$(lookup_field "$1" Pre-Depends)"
  echo "${pd:+$pd, }$d"
}

# Parse Debian Depends line → package names (drop versions/alts)
parse_deps() {
  local line="$1"
  [[ -z "$line" ]] && return 0
  echo "$line" | tr ',' '\n' | while read -r clause; do
    clause="$(echo "$clause" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -z "$clause" ]] && continue
    # take first alternative only
    first="${clause%%|*}"
    first="$(echo "$first" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    # strip version constraint
    name="${first%% *}"
    name="${name%%:*}"  # strip arch qualifier if present
    # skip arch-specific weirdness / empty
    case "$name" in
      ""|*"("* ) continue ;;
    esac
    # virtual/meta often missing — skip known noise
    case "$name" in
      debconf-2.0) echo debconf ;;
      *) echo "$name" ;;
    esac
  done
}

declare -A SEEN=()
QUEUE=("${SEED[@]}")
DOWNLOADED=0
FAILED=()

download_pkg() {
  local pkg="$1"
  local fn url base
  fn="$(lookup_filename "$pkg")"
  if [[ -z "$fn" ]]; then
    echo "SKIP (not in indexes): $pkg" >&2
    FAILED+=("$pkg")
    return 1
  fi
  local dest_name
  dest_name="$(basename "$fn")"
  if [[ -f "$OUT/$dest_name" ]]; then
    echo "have: $dest_name"
    return 0
  fi
  # Prefer apt-get download when candidate exists (handles redirects/mirrors)
  if apt-cache show "${pkg}:armhf" >/dev/null 2>&1; then
    if (cd "$OUT" && apt-get download "${pkg}:armhf" >/dev/null 2>&1); then
      echo "apt: $pkg"
      DOWNLOADED=$((DOWNLOADED + 1))
      return 0
    fi
  fi
  # Filename is relative to archive root; choose base by path prefix heuristics
  case "$fn" in
    pool/main/*|pool/contrib/*|pool/non-free* )
      # try rpi first for pool paths that exist there, else debian
      for base in \
        http://archive.raspberrypi.com/debian \
        http://raspbian.raspberrypi.com/raspbian \
        http://deb.debian.org/debian \
        http://deb.debian.org/debian-security
      do
        url="$base/$fn"
        if curl -fsSL -o "$OUT/$dest_name.part" "$url"; then
          mv "$OUT/$dest_name.part" "$OUT/$dest_name"
          echo "curl: $pkg <- $base"
          DOWNLOADED=$((DOWNLOADED + 1))
          return 0
        fi
        rm -f "$OUT/$dest_name.part"
      done
      ;;
    *)
      for base in \
        http://archive.raspberrypi.com/debian \
        http://raspbian.raspberrypi.com/raspbian \
        http://deb.debian.org/debian
      do
        url="$base/$fn"
        if curl -fsSL -o "$OUT/$dest_name.part" "$url"; then
          mv "$OUT/$dest_name.part" "$OUT/$dest_name"
          echo "curl: $pkg <- $base"
          DOWNLOADED=$((DOWNLOADED + 1))
          return 0
        fi
        rm -f "$OUT/$dest_name.part"
      done
      ;;
  esac
  echo "FAIL: $pkg ($fn)" >&2
  FAILED+=("$pkg")
  return 1
}

echo "OUT=$OUT"
while ((${#QUEUE[@]})); do
  pkg="${QUEUE[0]}"
  QUEUE=("${QUEUE[@]:1}")
  [[ -n "${SEEN[$pkg]:-}" ]] && continue
  SEEN[$pkg]=1
  if ! download_pkg "$pkg"; then
    continue
  fi
  deps_line="$(lookup_depends "$pkg" || true)"
  while read -r dep; do
    [[ -z "$dep" ]] && continue
    [[ -n "${SEEN[$dep]:-}" ]] && continue
    QUEUE+=("$dep")
  done < <(parse_deps "$deps_line")
done

echo "---"
echo "debs in $OUT: $(find "$OUT" -maxdepth 1 -name '*.deb' | wc -l)"
du -sh "$OUT"
if ((${#FAILED[@]})); then
  echo "missing/failed (${#FAILED[@]}): ${FAILED[*]}" >&2
fi
ls -lh "$OUT" | head -50
rm -rf "$IDX"
echo "DONE"
