#!/bin/bash
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
echo "=== config ==="
grep -E 'transport:|whep_ingest:|nvr_host:' config.yaml || true
echo "=== health ==="
curl -sS http://127.0.0.1:8080/api/health | python3 -m json.tool | head -40
echo "=== cams ==="
curl -sS http://127.0.0.1:8080/api/cams | python3 -c '
import sys,json
for c in json.load(sys.stdin).get("cameras") or []:
    print(c.get("id"), c.get("online"), c.get("ip"), c.get("age_s"))
'
echo "=== mediamtx ==="
systemctl --user is-active bhvr-mediamtx.service 2>/dev/null || systemctl is-active bhvr-mediamtx.service 2>/dev/null || true
pgrep -af mediamtx | head -3 || true
curl -sS -m 3 -o /dev/null -w "mtx_cam0=%{http_code}\n" -X OPTIONS http://127.0.0.1:8889/bhvr-cam0/whep || true
echo "=== whep/start cam0 ==="
curl -sS -m 90 -X POST http://127.0.0.1:8080/api/preview/bhvr-cam0/whep/start || true
echo
echo "=== whep/start cam1 ==="
curl -sS -m 90 -X POST http://127.0.0.1:8080/api/preview/bhvr-cam1/whep/start || true
echo
echo "=== health after ==="
curl -sS http://127.0.0.1:8080/api/health | python3 -c 'import sys,json; h=json.load(sys.stdin); print(h.get("preview_transport"), h.get("preview_idle"))'
echo "=== uvicorn errors ==="
tail -50 uvicorn.log | grep -iE 'error|fail|whep|traceback|400|500' || tail -20 uvicorn.log
echo DIAG_BLACK_DONE
