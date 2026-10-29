#!/bin/bash
set -euo pipefail
cp -f /tmp/bhvr-ks/kiosk_settings.py "$HOME/bhvr-kiosk/app/kiosk_settings.py"
pkill -f 'uvicorn app.main:app' || true
sleep 1
cd "$HOME/bhvr-kiosk"
.venv/bin/python -c 'from app.kiosk_settings import push_soft_set_to_cam, cam_tree; print("mod_ok")'
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 30); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.3
done
# Wait for cam3 SSH
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=6 -o StrictHostKeyChecking=accept-new)
for i in $(seq 1 15); do
  if ssh "${KEY[@]}" admin@192.168.7.28 hostname >/dev/null 2>&1; then
    echo cam3_ssh_ok
    break
  fi
  sleep 1
done
bash /tmp/_smoke_usb_push.sh bhvr-cam3
