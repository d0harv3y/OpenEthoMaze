#!/bin/bash
# Bring up all 4 idle WHEP publishers without restarting uvicorn.
set -euo pipefail
cp -f /tmp/bhvr-htu/index.html /home/admin/bhvr-kiosk/app/templates/index.html 2>/dev/null || true
grep -n 'fail (tap LIVE)' /home/admin/bhvr-kiosk/app/templates/index.html | head -3 || true
echo "=== before ==="
curl -sS http://127.0.0.1:8080/api/health | python3 -c 'import sys,json; h=json.load(sys.stdin); print("idle", h.get("preview_idle"))'
for c in bhvr-cam0 bhvr-cam1 bhvr-cam2 bhvr-cam3; do
  echo "=== $c ==="
  code=$(curl -sS -m 180 -o "/tmp/whep_${c}.json" -w "%{http_code}" -X POST "http://127.0.0.1:8080/api/preview/${c}/whep/start" || echo fail)
  echo "http=$code $(head -c 160 "/tmp/whep_${c}.json" 2>/dev/null || true)"
  sleep 3
done
echo "=== after ==="
curl -sS http://127.0.0.1:8080/api/health | python3 -c 'import sys,json; h=json.load(sys.stdin); print("idle", h.get("preview_idle"), "transport", h.get("preview_transport"))'
ps -ef | grep -E 'rpicam-vid -n -t 0' | grep -v grep | wc -l | xargs -I{} echo "rpicam_count={}"
