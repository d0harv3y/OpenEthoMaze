#!/bin/bash
# Hard-restart bhvr-kiosk uvicorn (pkill -f quoting is fragile over nested SSH).
set -euxo pipefail
KIOSK="${HOME}/bhvr-kiosk"
cd "$KIOSK"

# Kill anything listening on 8080 or matching uvicorn app.main
pids=$(pgrep -f '[u]vicorn app.main' || true)
if [[ -n "${pids}" ]]; then
  echo "killing: $pids"
  kill -9 $pids || true
fi
sleep 1
# Also by port if still bound
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8080/tcp 2>/dev/null || true
fi
sleep 1

nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
sleep 3
pgrep -af '[u]vicorn app.main'
curl -sS --max-time 5 http://127.0.0.1:8080/api/health
echo

.venv/bin/python - <<'PY'
import inspect
import app.main as m
src = inspect.getsource(m.api_preview)
print("HAS_OLD_REJECT", "recording focus uses mpegts tee" in src)
print("HAS_NEW_TEE", "Multi-cam tees OK" in src)
assert "recording focus uses mpegts tee" not in src
assert "Multi-cam tees OK" in src
print("CODE_OK")
PY
