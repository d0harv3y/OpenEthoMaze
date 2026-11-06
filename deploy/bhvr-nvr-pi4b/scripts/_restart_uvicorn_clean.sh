#!/bin/bash
set -euxo pipefail
pkill -9 -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 2
pgrep -af uvicorn || echo "no uvicorn"
cd "$HOME/bhvr-kiosk"
grep -E 'transport:|whep_ingest:' config.yaml
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >"$HOME/bhvr-kiosk/uvicorn.log" 2>&1 &
sleep 3
curl -sS http://127.0.0.1:8080/api/health
echo
pgrep -af 'uvicorn app.main' || true
echo UVICORN_CLEAN_DONE
