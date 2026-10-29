#!/bin/bash
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
grep -n 'env_stats' app/main.py | head -5
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >"$HOME/bhvr-kiosk/uvicorn.log" 2>&1 &
sleep 2
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
ssh "${KEY[@]}" admin@192.168.7.41 'python3 /usr/local/bin/bhvr-cam-announce' || true
ssh "${KEY[@]}" admin@192.168.7.27 'python3 /usr/local/bin/bhvr-cam-announce' || true
sleep 1
curl -sS http://127.0.0.1:8080/api/cams | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
for want in ("bhvr-cam0", "bhvr-cam1"):
    for c in d.get("cameras") or []:
        if c.get("id") == want:
            print(want, {k: c.get(k) for k in ("temp_c", "rh_pct", "env", "ts")})
'
.venv/bin/python -m pytest tests/test_env_jsonl.py -q || pip_install_hint=1
echo KIOSK_RESTART_DONE
