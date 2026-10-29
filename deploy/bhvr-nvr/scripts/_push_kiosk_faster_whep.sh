#!/bin/bash
set -euo pipefail
cp -f /tmp/kiosk_main.py "$HOME/bhvr-kiosk/app/main.py"
pkill -f 'uvicorn app.main:app' || true
sleep 1
cd "$HOME/bhvr-kiosk"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 25); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.3
done
echo restarted
# stop then cold-start time
curl -sS -m 5 -X POST 'http://127.0.0.1:8080/api/preview/stop?cam_id=bhvr-cam0' >/dev/null 2>&1 || true
sleep 0.5
start=$(date +%s.%N)
code=$(curl -sS -m 60 -X POST http://127.0.0.1:8080/api/preview/bhvr-cam0/whep/start -o /tmp/whep0.json -w '%{http_code}')
end=$(date +%s.%N)
python3 -c "print('whep_http', '$code', 'seconds', round(float('$end')-float('$start'), 2))"
head -c 160 /tmp/whep0.json; echo
