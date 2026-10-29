#!/bin/bash
# Start MediaMTX now; print how to enable systemd (needs sudo once).
set -uo pipefail
ROOT="$HOME/bhvr-mediamtx"
UNIT_SRC="$HOME/deploy/bhvr-nvr/systemd/bhvr-mediamtx.service"
[[ -x "$ROOT/mediamtx" ]] || { echo "missing $ROOT/mediamtx"; exit 1; }
[[ -f "$ROOT/mediamtx.yml" ]] || { echo "missing $ROOT/mediamtx.yml"; exit 1; }

if systemctl is-active --quiet bhvr-mediamtx.service 2>/dev/null; then
  echo "systemd bhvr-mediamtx already active"
  systemctl --no-pager --full status bhvr-mediamtx.service | head -12
  exit 0
fi

pkill -x mediamtx 2>/dev/null || true
sleep 0.3
nohup "$ROOT/mediamtx" "$ROOT/mediamtx.yml" >/tmp/mediamtx.log 2>&1 &
sleep 1
if pgrep -x mediamtx >/dev/null; then
  echo "mediamtx running pid=$(pgrep -x mediamtx)"
  head -15 /tmp/mediamtx.log
else
  echo "FAILED to start"
  cat /tmp/mediamtx.log
  exit 1
fi

echo
echo "=== make automatic (run once with sudo) ==="
echo "  sudo cp $UNIT_SRC /etc/systemd/system/bhvr-mediamtx.service"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now bhvr-mediamtx.service"
echo "  # then pkill the nohup copy if systemd took over"
if [[ -f "$UNIT_SRC" ]]; then
  if sudo -n true 2>/dev/null; then
    sudo cp "$UNIT_SRC" /etc/systemd/system/bhvr-mediamtx.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now bhvr-mediamtx.service
    sleep 1
    systemctl --no-pager --full status bhvr-mediamtx.service | head -15
  else
    echo "(no passwordless sudo on NVR — paste the three sudo lines above)"
  fi
fi
