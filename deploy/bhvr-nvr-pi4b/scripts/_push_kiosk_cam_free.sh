#!/bin/bash
set -euo pipefail
DEST="$HOME/bhvr-kiosk"
cp -f /tmp/kiosk_main.py "$DEST/app/main.py"
cp -f /tmp/kiosk_preview.py "$DEST/app/preview.py"
cp -f /tmp/kiosk_index.html "$DEST/app/templates/index.html"
cd "$DEST"
.venv/bin/python -c 'from app.preview import cam_free_encode_remote; print("ok", len(cam_free_encode_remote()))'
pkill -f 'uvicorn app.main:app' || true
sleep 1
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 25); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.3
done
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15)
# Free any wifi online cams' orphan encodes, then litmus whep on first wifi cam
CAM=""; IP=""
eval "$(curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("online") and str(c.get("link"))=="wifi" and c.get("ip"):
        print("CAM=%r"%c["id"]); print("IP=%r"%c["ip"]); break
')"
if [[ -n "${IP:-}" ]]; then
  echo "freeing $CAM $IP"
  ssh "${KEY[@]}" "admin@$IP" 'pkill -9 rpicam-vid 2>/dev/null || true; pkill -9 -x ffmpeg 2>/dev/null || true; pgrep -a rpicam || echo no_rpicam'
  echo "=== whep/start ==="
  curl -sS -m 90 -X POST "http://127.0.0.1:8080/api/preview/${CAM}/whep/start" -w "\nHTTP %{http_code}\n" | tail -20
fi
echo DONE
