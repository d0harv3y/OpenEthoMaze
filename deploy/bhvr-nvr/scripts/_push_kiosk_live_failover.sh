#!/bin/bash
# Push kiosk LIVE path-failover (main.py + index.html) and restart uvicorn.
set -euo pipefail
DEST="${HOME}/bhvr-kiosk"
test -f /tmp/kiosk_main.py && test -f /tmp/kiosk_index.html
cp -f /tmp/kiosk_main.py "$DEST/app/main.py"
cp -f /tmp/kiosk_index.html "$DEST/app/templates/index.html"
mkdir -p "$DEST/tests"
if [[ -f /tmp/test_roster_hosts.py ]]; then
  cp -f /tmp/test_roster_hosts.py "$DEST/tests/test_roster_hosts.py"
fi
cd "$DEST"
.venv/bin/python -c 'from app.main import _roster_hosts_for_cam, ssh_connect_timeout_for_host; print("import_ok", ssh_connect_timeout_for_host("1.2.3.4", mismatch=True))'
# Restart kiosk web if we can find it
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
  echo "WARN: no running kiosk — start manually"
fi
for _ in $(seq 1 20); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.3
done
curl -sS -m 5 http://127.0.0.1:8080/api/health | head -c 200; echo
echo KIOSK_LIVE_FAILOVER_OK
