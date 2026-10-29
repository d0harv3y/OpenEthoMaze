#!/bin/bash
# Install Kiosk settings files staged in /tmp/bhvr-ks/ and restart uvicorn.
set -euo pipefail
DEST="${HOME}/bhvr-kiosk"
SRC="${1:-/tmp/bhvr-ks}"
test -f "$SRC/kiosk_settings.py"
test -f "$SRC/main.py"
test -f "$SRC/index.html"
cp -f "$SRC/kiosk_settings.py" "$DEST/app/kiosk_settings.py"
cp -f "$SRC/main.py" "$DEST/app/main.py"
cp -f "$SRC/index.html" "$DEST/app/templates/index.html"
cp -f "$SRC/config.example.yaml" "$DEST/config.example.yaml"
mkdir -p "$HOME/deploy/bhvr-nvr/sudoers"
if [[ -f "$SRC/bhvr-nvr-kiosk" ]]; then
  cp -f "$SRC/bhvr-nvr-kiosk" "$HOME/deploy/bhvr-nvr/sudoers/bhvr-nvr-kiosk"
fi
cd "$DEST"
.venv/bin/python -c 'from app import kiosk_settings; from app.main import app; print("import_ok", len(kiosk_settings.SOFT_INSTALL))'
if systemctl --user restart bhvr-kiosk-web.service 2>/dev/null; then
  echo restarted_user_unit
elif pgrep -f 'uvicorn app.main:app' >/dev/null; then
  pkill -f 'uvicorn app.main:app' || true
  sleep 1
  nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
    >>/tmp/kiosk-web.log 2>&1 &
  disown || true
  echo restarted_uvicorn
else
  nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
    >>/tmp/kiosk-web.log 2>&1 &
  disown || true
  echo started_uvicorn
fi
for _ in $(seq 1 25); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.4
done
echo '--- health ---'
curl -sS -m 5 http://127.0.0.1:8080/api/health | head -c 240; echo
echo '--- kiosk status ---'
curl -sS -m 45 http://127.0.0.1:8080/api/kiosk/status | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
print("soft", d.get("soft_present"), "/", d.get("soft_total"))
g = d.get("git") or {}
print("git", g.get("describe"), "dirty", g.get("dirty"), "err", g.get("error"))
print("eligible", [c["id"] for c in d.get("eligible", []) if c.get("eligible")])
print("data_root", d.get("data_root"))
'
if [[ -d "$HOME/OpenEthoMaze/deploy/bhvr-cam" ]]; then
  echo "cam_tree: $HOME/OpenEthoMaze/deploy/bhvr-cam"
else
  echo "WARN: missing $HOME/OpenEthoMaze/deploy/bhvr-cam (USB push needs git checkout)"
fi
echo KIOSK_SETTINGS_DEPLOY_OK
