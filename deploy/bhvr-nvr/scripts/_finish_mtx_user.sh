#!/bin/bash
# Finish deploy without systemd (sudo needs TTY). Run ON NVR.
set -euxo pipefail
SRC=/tmp/bhvr-mtx-deploy
ROOT="$HOME/bhvr-mediamtx"
KIOSK="$HOME/bhvr-kiosk"

# Ensure config/binary present from prior install step
test -x "$ROOT/mediamtx"
test -f "$ROOT/mediamtx.yml"
cp -f "$HOME/deploy/bhvr-nvr/mediamtx/mediamtx.yml" "$ROOT/mediamtx.yml" 2>/dev/null || true
# re-inject hosts
python3 - <<'PY'
from pathlib import Path
import re, subprocess
yml = Path.home() / "bhvr-mediamtx" / "mediamtx.yml"
text = yml.read_text(encoding="utf-8")
hosts = ["127.0.0.1", "192.168.7.1"]
try:
    out = subprocess.check_output(["ip", "-4", "-br", "addr", "show", "wlan0"], text=True)
    m = re.search(r"(\d+\.\d+\.\d+\.\d+)", out)
    if m and m.group(1) not in hosts:
        hosts.append(m.group(1))
except Exception:
    pass
line = "webrtcAdditionalHosts: [" + ", ".join(hosts) + "]"
text2, n = re.subn(r"^webrtcAdditionalHosts:.*$", line, text, count=1, flags=re.M)
assert n == 1, "hosts line"
yml.write_text(text2, encoding="utf-8")
print(line)
PY

# Kiosk sync
cp -f "$SRC/preview.py" "$KIOSK/app/preview.py"
cp -f "$SRC/main.py" "$KIOSK/app/main.py"
cp -f "$SRC/index.html" "$KIOSK/app/templates/index.html"
cp -f "$SRC/mediamtx-reader.js" "$KIOSK/app/static/mediamtx-reader.js"
cp -f "$SRC/config.example.yaml" "$KIOSK/config.example.yaml"
python3 - <<'PY'
from pathlib import Path
import yaml
p = Path.home() / "bhvr-kiosk" / "config.yaml"
raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
prev = raw.setdefault("preview", {})
prev["transport"] = "whep"
prev.setdefault("udp_port", 15550)
prev.setdefault("mediamtx_http", "http://127.0.0.1:8889")
prev.setdefault("nvr_host", "192.168.7.1")
p.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
print("preview=", prev)
PY

# Kill old mediamtx / free port
pkill -x mediamtx 2>/dev/null || true
fuser -k 15550/udp 2>/dev/null || true
fuser -k 8889/tcp 2>/dev/null || true
sleep 1
nohup "$ROOT/mediamtx" "$ROOT/mediamtx.yml" >/tmp/mediamtx.log 2>&1 &
echo "mediamtx_pid=$!"
sleep 2
head -40 /tmp/mediamtx.log || true
ss -ulnp | grep -E '15550|8189' || true
ss -tlnp | grep -E '8889|8189' || true

# Restart kiosk uvicorn
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
cd "$KIOSK"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >/tmp/kiosk-uvicorn.log 2>&1 &
echo "kiosk_pid=$!"
sleep 2
curl -sS http://127.0.0.1:8080/api/health || true
echo
