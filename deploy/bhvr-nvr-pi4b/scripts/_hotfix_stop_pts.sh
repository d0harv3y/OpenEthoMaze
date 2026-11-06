#!/bin/bash
set -euxo pipefail
cp -f /tmp/bhvr-ts-science/main.py "$HOME/bhvr-kiosk/app/main.py"
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
pkill -f 'uvicorn app.main' 2>/dev/null || true
sleep 1
cd "$HOME/bhvr-kiosk"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 20); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.5
done
echo "=== stop session ==="
curl -sS -m 180 -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8080/api/session/stop
echo
echo "=== health ==="
curl -sS http://127.0.0.1:8080/api/health; echo
echo "=== session folder ==="
ls -la /media/admin/random/bhvr/sub-ts-test/ses-20261021T173512Z/ 2>/dev/null | head -30 || true
echo "=== pts file xxd ==="
xxd /media/admin/random/bhvr/sub-ts-test/ses-20261021T173512Z/bhvr-cam1_timestamps.pts 2>/dev/null | head -3 || true
echo "=== capture log tails ==="
for c in 0 1 2 3; do
  f=/media/admin/random/bhvr/sub-ts-test/ses-20261021T173512Z/bhvr-cam${c}_capture.log
  if [[ -f "$f" ]]; then echo "-- cam$c --"; tail -15 "$f"; fi
done
echo "Logging: uvicorn → /tmp/kiosk-web.log (no separate debug flag; raise log_level via uvicorn if needed)"
