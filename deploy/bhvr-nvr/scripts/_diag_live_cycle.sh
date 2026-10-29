#!/bin/bash
# Snapshot roster + which idle publishers are alive + recent kiosk log lines.
set -uo pipefail
cd "$HOME/bhvr-kiosk"
echo "=== api/cams ==="
curl -sS http://127.0.0.1:8080/api/cams | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
for c in d.get("cameras") or []:
    print(c.get("id"), "online="+str(c.get("online")), "age="+str(c.get("age_s")), "ip="+str(c.get("ip")))
'
echo "=== health preview_idle ==="
curl -sS http://127.0.0.1:8080/api/health | .venv/bin/python -c '
import sys, json
h = json.load(sys.stdin)
print("preview_idle", h.get("preview_idle"))
print("roster_size", h.get("roster_size"), "active", h.get("active"))
' 2>/dev/null || curl -sS http://127.0.0.1:8080/api/health | head -c 800
echo
echo "=== uvicorn tail (stall/fail/whep) ==="
grep -E 'stall|preview failed|whep|live retry|ERROR' "$HOME/bhvr-kiosk/uvicorn.log" 2>/dev/null | tail -40 || true
echo DIAG_DONE
