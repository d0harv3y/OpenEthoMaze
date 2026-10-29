#!/bin/bash
# Download armhf runtime debs for air-gap firstboot (run on online armhf Pi OS).
# Usage: sudo bash fetch_offline_debs.sh [OUT_DIR]
# Default OUT_DIR: ../debs next to this tree (deploy/bhvr-cam/debs).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$SCRIPT_DIR/../debs}"
ARCH="$(dpkg --print-architecture)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root (apt-get download-only)" >&2
  exit 1
fi
if [[ "$ARCH" != "armhf" ]]; then
  echo "WARN: arch=$ARCH (fleet cams are armhf / Pi Zero W 32-bit). Aborting." >&2
  exit 1
fi

mkdir -p "$OUT"
# Clear only .deb we own in OUT — leave README/gitignore.
find "$OUT" -maxdepth 1 -name '*.deb' -delete

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --download-only --reinstall --no-install-recommends \
  rpicam-apps \
  ffmpeg

shopt -s nullglob
debs=(/var/cache/apt/archives/*.deb)
if ((${#debs[@]} == 0)); then
  echo "no debs in /var/cache/apt/archives" >&2
  exit 1
fi
cp -v "${debs[@]}" "$OUT/"
echo "wrote ${#debs[@]} packages → $OUT"
du -sh "$OUT"
ls "$OUT"/*.deb | wc -l
