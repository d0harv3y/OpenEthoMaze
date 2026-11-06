#!/bin/bash
set -euxo pipefail
for c in bhvr-cam2 bhvr-cam3; do
  echo "=== $c ==="
  curl -sS -m 90 -X POST "http://127.0.0.1:8080/api/preview/${c}/whep/start" || true
  echo
done
curl -sS http://127.0.0.1:8080/api/health | python3 -c 'import sys,json; h=json.load(sys.stdin); print("preview_idle", h.get("preview_idle"))'
