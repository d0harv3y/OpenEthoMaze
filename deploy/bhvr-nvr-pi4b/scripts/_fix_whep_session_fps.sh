#!/bin/bash
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
cp /tmp/bhvr-htu/main.py app/main.py
cp /tmp/bhvr-htu/index.html app/templates/index.html
cp /tmp/bhvr-htu/encode_ask.py app/encode_ask.py
# Ensure operator soft_fps is 30 if file exists / create default
python3 - <<'PY'
from pathlib import Path
import json
root = Path("/media/admin/random/bhvr")
p = root / ".kiosk_operator.json"
if p.is_file():
    st = json.loads(p.read_text(encoding="utf-8"))
else:
    st = {"profile": "lite", "soft_fps": 30, "output_subdir": "", "chunk_minutes": 20, "cameras": {}}
st["soft_fps"] = 30
if not st.get("profile"):
    st["profile"] = "lite"
p.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
print("operator", st.get("profile"), st.get("soft_fps"))
PY
curl -sS -X POST http://127.0.0.1:8080/api/preview/stop || true
pkill -9 -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 2
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >uvicorn.log 2>&1 &
sleep 3
# Prove whep/start reports 30fps path via rpicam line in cam log after start
curl -sS -m 180 -X POST http://127.0.0.1:8080/api/preview/bhvr-cam0/whep/start
echo
sleep 1
grep -E 'framerate|640|480' /tmp/bhvr-preview-bhvr-cam0-cam.log | tail -5 || true
# Show remote cmdline hint from process list
pgrep -af 'rpicam-vid' | head -4 || true
echo FPS_FIX_DONE
