#!/bin/bash
set -eu
echo "=== health ==="
curl -sS -m 5 http://127.0.0.1:8080/api/health || true
echo
echo "=== session ==="
curl -sS -m 5 http://127.0.0.1:8080/api/session || true
echo
echo "=== active.json ==="
cat "$HOME/bhvr-kiosk"/../ 2>/dev/null || true
python3 - <<'PY'
from pathlib import Path
import json
# common locations
for p in [
    Path.home() / "bhvr-kiosk" / "active.json",
    Path("/media/admin/random/bhvr/active.json"),
    Path("/data/bhvr/active.json"),
]:
    print("try", p, p.is_file())
    if p.is_file():
        print(p.read_text()[:800])
PY
# find active from app
cd "$HOME/bhvr-kiosk" && .venv/bin/python - <<'PY'
from app.main import active_path, data_root, load_config
print("data_root", data_root())
print("active_path", active_path(), active_path().is_file())
if active_path().is_file():
    print(active_path().read_text()[:1200])
PY
echo "=== kiosk log tail ==="
tail -80 /tmp/kiosk-web.log || true
echo "=== traceback grep ==="
grep -nE 'Error|Traceback|Exception|500|stop|FAIL|SyntaxError' /tmp/kiosk-web.log | tail -60 || true
echo "=== try stop ==="
curl -sS -m 120 -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8080/api/session/stop || true
echo "=== log after stop ==="
tail -40 /tmp/kiosk-web.log || true
