#!/bin/bash
# Drop paint-decimate slider; tee_queue_max default 512.
set -euxo pipefail
SRC=/tmp/bhvr-no-decimate
DEST="$HOME/bhvr-kiosk"
cp -f "$SRC/preview.py" "$DEST/app/preview.py"
cp -f "$SRC/main.py" "$DEST/app/main.py"
cp -f "$SRC/index.html" "$DEST/app/templates/index.html"
grep -n "tee_queue_max\|decimate\|paint every" "$DEST/app/preview.py" "$DEST/app/main.py" "$DEST/app/templates/index.html" | head -30
cd "$DEST"
# Ensure live config has tee_queue_max (idempotent).
"$DEST/.venv/bin/python" - <<'PY'
from pathlib import Path
import yaml
p = Path.home() / "bhvr-kiosk" / "config.yaml"
raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
prev = raw.setdefault("preview", {})
if "tee_queue_max" not in prev:
    prev["tee_queue_max"] = 512
    p.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    print("config: set preview.tee_queue_max=512")
else:
    print("config: tee_queue_max=", prev.get("tee_queue_max"))
PY
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
nohup "$DEST/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 25); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.4
done
"$DEST/.venv/bin/python" -c 'from app.preview import preview_settings; s=preview_settings({"preview":{}}); assert s.tee_queue_max==512; print("tee_ok", s.tee_queue_max)'
curl -sS http://127.0.0.1:8080/api/health | head -c 300; echo
# Slider gone from HTML
! grep -q 'decimate-n' "$DEST/app/templates/index.html"
echo DEPLOY_OK
