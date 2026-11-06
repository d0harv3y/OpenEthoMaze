#!/bin/bash
set -euxo pipefail
cp -f /tmp/bhvr-ts-science/preview.py "$HOME/bhvr-kiosk/app/preview.py"
cp -f /tmp/bhvr-ts-science/main.py "$HOME/bhvr-kiosk/app/main.py"
grep -n "pkill -x ffmpeg" "$HOME/bhvr-kiosk/app/preview.py" | head -5
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
cd "$HOME/bhvr-kiosk"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 20); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.5
done
curl -sS http://127.0.0.1:8080/api/health; echo
bash /tmp/_probe_science_ts_pipe.sh
