#!/usr/bin/env bash
# Soft-restart kiosk uvicorn after deploying app files to ~/bhvr-kiosk.
set -euo pipefail
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
cd "${HOME}/bhvr-kiosk"
# shellcheck disable=SC2086
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2
code=$(curl -sS -o /tmp/op_settings.json -w '%{http_code}' http://127.0.0.1:8080/api/operator/settings || echo fail)
echo "HTTP ${code}"
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/op_settings.json")
if not p.is_file() or p.stat().st_size == 0:
    raise SystemExit("no settings body")
s = json.loads(p.read_text(encoding="utf-8"))["settings"]
print("h5_pack", s.get("h5_pack"), "tag", repr(s.get("recording_tag")))
PY
