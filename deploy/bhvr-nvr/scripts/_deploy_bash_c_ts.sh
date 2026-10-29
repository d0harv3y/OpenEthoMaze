#!/bin/bash
set -euxo pipefail
cp -f /tmp/bhvr-ts-science/preview.py "$HOME/bhvr-kiosk/app/preview.py"
cp -f /tmp/bhvr-ts-science/main.py "$HOME/bhvr-kiosk/app/main.py"
grep -n "_ssh_bash_c\|bash -c" "$HOME/bhvr-kiosk/app/preview.py" | head -10
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
cd "$HOME/bhvr-kiosk"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 25); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.4
done
curl -sS http://127.0.0.1:8080/api/health; echo
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
IP=10.248.233.15
REMOTE=$(.venv/bin/python -c 'from app.preview import cam_live_ssh_mpegts_remote, preview_settings; print(cam_live_ssh_mpegts_remote(preview_settings({"preview":{"transport":"mpegts","buffer_count":3}})))')
echo "remote_prefix=${REMOTE:0:20}"
timeout 10 ssh "${KEY[@]}" "admin@$IP" "$REMOTE" > /tmp/idle_ssh.ts 2>/tmp/idle_ssh.err || true
wc -c /tmp/idle_ssh.ts
tail -3 /tmp/idle_ssh.err || true
test "$(wc -c </tmp/idle_ssh.ts)" -gt 10000 && echo PIPE_OK || echo PIPE_FAIL
