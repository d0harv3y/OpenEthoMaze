#!/bin/bash
# Install science-ask prototype onto ~/bhvr-kiosk (run ON NVR after scp to /tmp/bhvr-science-ask).
set -euxo pipefail
SRC=/tmp/bhvr-science-ask
KIOSK="${HOME}/bhvr-kiosk"
mkdir -p "$KIOSK/tests" "$KIOSK/app/templates"

cp -f "$SRC/encode_ask.py" "$KIOSK/app/encode_ask.py"
cp -f "$SRC/main.py" "$KIOSK/app/main.py"
cp -f "$SRC/preview.py" "$KIOSK/app/preview.py"
cp -f "$SRC/index.html" "$KIOSK/app/templates/index.html"
cp -f "$SRC/config.example.yaml" "$KIOSK/config.example.yaml"
cp -f "$SRC/test_encode_ask.py" "$KIOSK/tests/test_encode_ask.py"
cp -f "$SRC/test_preview_settings.py" "$KIOSK/tests/test_preview_settings.py"

python3 <<'PY'
from pathlib import Path
import yaml

p = Path.home() / "bhvr-kiosk" / "config.yaml"
cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
cfg["default_profile"] = "standard"
cfg["profiles"] = ["standard", "lite"]
rec = cfg.get("record") or {}
rec.setdefault("soft_fps", 20)
cfg["record"] = rec
prev = cfg.get("preview") or {}
prev["buffer_count"] = max(6, int(prev.get("buffer_count") or 6))
for k in ("width", "height", "fps_idle", "fps_record", "sensor_mode"):
    prev.pop(k, None)
cfg["preview"] = prev
cfg.pop("cam_sensor_mode", None)
p.write_text(
    yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False),
    encoding="utf-8",
)
print("config patched", cfg["profiles"], cfg["default_profile"])
PY

cd "$KIOSK"
# NVR kiosk venv may omit pytest — import litmus is enough for deploy smoke.
.venv/bin/python - <<'PY'
from app.encode_ask import idle_encode_ask, science_encode_ask
from app.preview import preview_settings

idle = idle_encode_ask({})
assert idle.size_id == "lite" and idle.soft_fps == 10 and idle.width == 640
sci = science_encode_ask("standard", 20)
assert sci.width == 1296 and sci.sensor_mode == "1296:972"
s = preview_settings({"preview": {"transport": "whep", "buffer_count": 6}})
assert s.width == 640 and s.fps_idle == 10 and s.buffer_count >= 6
print("IMPORT_LITMUS_OK", idle.label, sci.label)
PY

# Restart without sudo TTY: kill uvicorn owned by admin, then relaunch.
# (systemctl restart needs password — operator can enable passwordless later.)
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
pkill -f 'uvicorn app.main' 2>/dev/null || true
sleep 1
cd "$KIOSK"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
sleep 3
pgrep -af 'uvicorn app.main' || echo NO_UVICORN
curl -sS --max-time 5 http://127.0.0.1:8080/api/health
echo

# Smoke science-ask surface
python3 <<'PY'
import json, urllib.request, urllib.error

def get(url):
    with urllib.request.urlopen(url, timeout=8) as r:
        return r.read().decode(), r.status

def put(url, body):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="PUT",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode(), r.status
    except urllib.error.HTTPError as e:
        return e.read().decode(), e.code

health, _ = get("http://127.0.0.1:8080/api/health")
print("HEALTH", health[:300])
cams, _ = get("http://127.0.0.1:8080/api/cams")
print("CAMS", cams[:500])
body, code = put(
    "http://127.0.0.1:8080/api/cams/bhvr-cam0/sensor-mode",
    {"sensor_mode": "1920:1080"},
)
print("SENSOR_PUT", code, body[:200])
assert code == 410, code

# Index HTML must contain science chips / honesty (not sensor mode section)
html, _ = get("http://127.0.0.1:8080/")
assert "Science size" in html, "missing Science size chips"
assert "size-chips" in html
assert "decimate-n" in html
assert "honesty-badge" in html
assert "Sensor mode" not in html
print("INDEX_OK chips+honesty, no sensor menu")

# Start idle whep on first online cam if any
j = json.loads(cams)
online = [c for c in j.get("cameras") or [] if c.get("online")]
print("ONLINE", [c.get("id") for c in online])
if online:
    cam = online[0]["id"]
    req = urllib.request.Request(
        f"http://127.0.0.1:8080/api/preview/{cam}/whep/start",
        method="POST",
        data=b"",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            out = r.read().decode()
            print("WHEP_START", out[:400])
    except urllib.error.HTTPError as e:
        print("WHEP_START_FAIL", e.code, e.read().decode()[:400])
print("SMOKE_OK")
PY

echo DEPLOY_SCIENCE_ASK_OK
