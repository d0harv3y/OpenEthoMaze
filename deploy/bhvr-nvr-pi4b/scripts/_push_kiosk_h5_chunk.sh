#!/bin/bash
# Deploy chunk-roll + H5 pack to ~/bhvr-kiosk and restart uvicorn.
set -euo pipefail
SRC="${1:-/tmp/bhvr-ks-h5}"
DEST="${HOME}/bhvr-kiosk"
test -f "$SRC/main.py"
test -f "$SRC/h5_archive.py"
test -f "$SRC/capture_sink.py"
cp -f "$SRC/main.py" "$DEST/app/main.py"
cp -f "$SRC/h5_archive.py" "$DEST/app/h5_archive.py"
cp -f "$SRC/capture_sink.py" "$DEST/app/capture_sink.py"
cp -f "$SRC/requirements.txt" "$DEST/requirements.txt" 2>/dev/null || true
cd "$DEST"
.venv/bin/pip install -q 'h5py>=3.11.0' 'numpy>=1.26.0'
.venv/bin/python -c 'from app import h5_archive; from app.capture_sink import CaptureSink; from app.main import app; print("import_ok", h5_archive.__name__)'
pkill -f 'uvicorn app.main:app' || true
sleep 1
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 30); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.3
done
curl -sS -m 5 http://127.0.0.1:8080/api/health | head -c 200; echo
echo KIOSK_H5_CHUNK_OK
