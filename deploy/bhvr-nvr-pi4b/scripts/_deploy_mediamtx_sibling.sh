#!/bin/bash
# Run ON NVR after scp of deploy tree pieces into /tmp/bhvr-mtx-deploy/
set -euxo pipefail
SRC=/tmp/bhvr-mtx-deploy
test -d "$SRC"

DEST="$HOME/deploy/bhvr-nvr"
mkdir -p "$DEST/mediamtx" "$DEST/systemd" "$DEST/scripts"
cp -f "$SRC/mediamtx.yml" "$DEST/mediamtx/mediamtx.yml"
cp -f "$SRC/bhvr-mediamtx.service" "$DEST/systemd/bhvr-mediamtx.service"
cp -f "$SRC/install_mediamtx.sh" "$DEST/scripts/install_mediamtx.sh"
chmod +x "$DEST/scripts/install_mediamtx.sh"
sed -i 's/\r$//' "$DEST/scripts/install_mediamtx.sh" \
  "$DEST/mediamtx/mediamtx.yml" \
  "$DEST/systemd/bhvr-mediamtx.service"

# Stop anything holding :15550 before MediaMTX binds it.
pkill -f 'ffmpeg.*15550' 2>/dev/null || true
fuser -k 15550/udp 2>/dev/null || true

MEDIAMTX_TAG=v1.21.2 bash "$DEST/scripts/install_mediamtx.sh"

# Sync kiosk app bits
KIOSK="$HOME/bhvr-kiosk"
if [[ -d "$KIOSK/app" ]]; then
  cp -f "$SRC/preview.py" "$KIOSK/app/preview.py"
  cp -f "$SRC/main.py" "$KIOSK/app/main.py"
  cp -f "$SRC/index.html" "$KIOSK/app/templates/index.html"
  cp -f "$SRC/mediamtx-reader.js" "$KIOSK/app/static/mediamtx-reader.js"
  if [[ -f "$SRC/config.example.yaml" ]]; then
    cp -f "$SRC/config.example.yaml" "$KIOSK/config.example.yaml"
  fi
  python3 - <<'PY'
from pathlib import Path
import yaml
p = Path.home() / "bhvr-kiosk" / "config.yaml"
raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
prev = raw.setdefault("preview", {})
prev["transport"] = "whep"
prev.setdefault("udp_port", 15550)
prev.setdefault("mediamtx_http", "http://127.0.0.1:8889")
prev.setdefault("nvr_host", "192.168.7.1")
p.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
print("preview=", prev)
PY
fi

echo DEPLOY_OK
