#!/bin/bash
set -euxo pipefail
cp -f /tmp/bhvr-ts-science/preview.py "$HOME/bhvr-kiosk/app/preview.py"
cp -f /tmp/bhvr-ts-science/main.py "$HOME/bhvr-kiosk/app/main.py"
grep -n "_popen_ssh_bash_s\|bash -s" "$HOME/bhvr-kiosk/app/main.py" | head -8
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
# Mimic kiosk: ssh bash -s <<< script
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
IP=10.248.233.15
SCRIPT=$(.venv/bin/python -c 'from app.preview import cam_live_ssh_mpegts_remote, preview_settings; print(cam_live_ssh_mpegts_remote(preview_settings({"preview":{"transport":"mpegts","buffer_count":3}})))')
timeout 10 ssh "${KEY[@]}" "admin@$IP" bash -s > /tmp/idle_bashs.ts 2>/tmp/idle_bashs.err <<<"$SCRIPT" || true
wc -c /tmp/idle_bashs.ts
tail -5 /tmp/idle_bashs.err || true
n=$(wc -c </tmp/idle_bashs.ts)
if [[ "$n" -gt 10000 ]]; then echo PIPE_OK bytes=$n; else echo PIPE_FAIL bytes=$n; exit 1; fi
curl -sS http://127.0.0.1:8080/api/health; echo
