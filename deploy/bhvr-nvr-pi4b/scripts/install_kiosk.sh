#!/bin/bash
# Install / refresh bhvr-kiosk on this NVR (run as admin).
set -euo pipefail

SRC="${1:-$HOME/deploy/bhvr-kiosk}"
DST="${HOME}/bhvr-kiosk"

if [[ ! -d "$SRC/app" ]]; then
  echo "usage: $0 [/path/to/bhvr-kiosk]" >&2
  echo "expected app/ under $SRC" >&2
  exit 1
fi

mkdir -p /data/bhvr
sudo chown "$USER:$USER" /data/bhvr

rsync -a --delete \
  --exclude .venv \
  --exclude config.yaml \
  --exclude '__pycache__' \
  "$SRC/" "$DST/"

if [[ ! -f "$DST/config.yaml" ]]; then
  cp "$DST/config.example.yaml" "$DST/config.yaml"
fi

python3 -m venv "$DST/.venv"
# shellcheck disable=SC1091
source "$DST/.venv/bin/activate"
pip install -U pip
pip install -r "$DST/requirements.txt"

python3 "$(dirname "$0")/push_nvr_ssh_pubkey.py" || true

sudo install -m 0644 "$DST/systemd/bhvr-kiosk-web.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bhvr-kiosk-web.service
sudo systemctl restart bhvr-kiosk-web.service

echo "kiosk web: http://127.0.0.1:8080"
echo "Paste NVR pubkey into each cam authorized_keys (script printed above)."
echo "Browser kiosk unit is optional — see systemd/bhvr-kiosk-browser.service"
