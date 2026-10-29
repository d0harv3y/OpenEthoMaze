#!/bin/bash
# Deploy Session settings / per-cam meta / lean chrome (grill 2026-10-22).
set -euxo pipefail
SRC=/tmp/bhvr-settings-grill
DEST="$HOME/bhvr-kiosk"
cp -f "$SRC/operator_state.py" "$DEST/app/operator_state.py"
cp -f "$SRC/main.py" "$DEST/app/main.py"
cp -f "$SRC/index.html" "$DEST/app/templates/index.html"
cp -f "$SRC/SETTINGS_GRILL.md" "$DEST/SETTINGS_GRILL.md"
mkdir -p "$DEST/tests"
cp -f "$SRC/test_operator_state.py" "$DEST/tests/test_operator_state.py"
cd "$DEST"
"$DEST/.venv/bin/python" -m pytest tests/test_operator_state.py -q || \
  "$DEST/.venv/bin/python" -c 'from app.operator_state import session_folder; from pathlib import Path; assert "ses-" in str(session_folder(Path("/tmp"),"","2026Z"))'
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
nohup "$DEST/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 25); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.4
done
curl -sS http://127.0.0.1:8080/api/operator/settings | head -c 500; echo
echo DEPLOY_OK
