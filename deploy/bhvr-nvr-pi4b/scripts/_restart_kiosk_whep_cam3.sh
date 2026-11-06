#!/bin/bash
set -uo pipefail
DEST="$HOME/bhvr-kiosk"
cp -f /tmp/kiosk_main.py "$DEST/app/main.py"
cp -f /tmp/kiosk_preview.py "$DEST/app/preview.py"
cp -f /tmp/kiosk_index.html "$DEST/app/templates/index.html"
cd "$DEST"
grep -n "cam_free_encode_remote\|Pipeline handler" app/preview.py | head -8
pkill -f 'uvicorn app.main:app' || true
sleep 1
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 30); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.3
done
echo "health_ok"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20)
ssh "${KEY[@]}" admin@10.248.235.74 'pkill -9 rpicam-vid 2>/dev/null||true; pkill -9 -x ffmpeg 2>/dev/null||true; sleep 0.5; echo pre; pgrep -a rpicam||echo no_rpicam' || echo wifi_ssh_fail
echo "=== whep ==="
curl -sS -m 100 -X POST http://127.0.0.1:8080/api/preview/bhvr-cam3/whep/start -w "\nHTTP %{http_code}\n" | tee /tmp/whep_cam3_out.txt | tail -30
echo "=== cam log ==="
tail -40 /tmp/bhvr-preview-bhvr-cam3-cam.log || true
echo "=== remux log ==="
tail -25 /tmp/bhvr-preview-bhvr-cam3-remux.log || true
