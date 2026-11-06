#!/bin/bash
# Stop thrash, restart kiosk once, bring up 4 WHEP publishers sequentially.
set -euxo pipefail
cd "$HOME/bhvr-kiosk"

echo "=== before ==="
curl -sS http://127.0.0.1:8080/api/health | python3 -c 'import sys,json; h=json.load(sys.stdin); print(h.get("preview_transport"), h.get("preview_idle"))' || true
grep -E 'location.reload|autoStartOnlineLives|live_preview_settings' app/templates/index.html app/main.py | head -20 || true

# Ensure UI bits that stop thrash are present
test -f /tmp/bhvr-htu/index.html && cp /tmp/bhvr-htu/index.html app/templates/index.html
test -f /tmp/bhvr-htu/main.py && cp /tmp/bhvr-htu/main.py app/main.py
test -f /tmp/bhvr-htu/preview.py && cp /tmp/bhvr-htu/preview.py app/preview.py
test -f /tmp/bhvr-htu/encode_ask.py && cp /tmp/bhvr-htu/encode_ask.py app/encode_ask.py

# Kill browser-driven storm: stop previews + uvicorn
curl -sS -X POST http://127.0.0.1:8080/api/preview/stop || true
pkill -9 -f 'uvicorn app.main:app' 2>/dev/null || true
pkill -f 'rpicam-vid -n -t 0' 2>/dev/null || true
sleep 2

# Confirm no empty-grid reload in template
if grep -q 'location.reload()' app/templates/index.html; then
  # Strip only the empty-grid auto-reload block if somehow reintroduced
  python3 - <<'PY'
from pathlib import Path
p = Path("app/templates/index.html")
t = p.read_text(encoding="utf-8")
# Remove the old empty-grid interval if present
import re
t2 = re.sub(
    r"\n\s*\{%\s*if not active\s*%\}.*?\{%\s*endif\s*%\}\n",
    "\n",
    t,
    count=1,
    flags=re.S,
)
# Also neutralize any remaining setInterval that only reloads when liveSessions empty
t2 = t2.replace(
    "location.reload();\n      }\n    }, 20000);",
    "/* empty-grid reload disabled */\n      }\n    }, 20000);",
)
if "Empty-grid auto-reload disabled" not in t2 and "empty-grid reload disabled" not in t2:
    # ensure comment marker exists near autoStart
    t2 = t2.replace(
        "setTimeout(autoStartOnlineLives, 400);",
        "setTimeout(autoStartOnlineLives, 400);\n    // Empty-grid auto-reload disabled",
    )
p.write_text(t2, encoding="utf-8")
print("template_reload_scrubbed")
PY
fi

# Operator fps 30
python3 - <<'PY'
from pathlib import Path
import json
root = Path("/media/admin/random/bhvr")
p = root / ".kiosk_operator.json"
st = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {
  "profile":"lite","soft_fps":30,"output_subdir":"","chunk_minutes":20,"cameras":{}
}
st["soft_fps"] = 30
st["profile"] = st.get("profile") or "lite"
p.write_text(json.dumps(st, indent=2)+"\n", encoding="utf-8")
print("operator", st["profile"], st["soft_fps"])
PY

nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >uvicorn.log 2>&1 &
sleep 3

for c in bhvr-cam0 bhvr-cam1 bhvr-cam2 bhvr-cam3; do
  echo "=== $c ==="
  code=$(curl -sS -m 180 -o /tmp/whep_$c.json -w "%{http_code}" -X POST "http://127.0.0.1:8080/api/preview/${c}/whep/start" || echo fail)
  echo "http=$code $(head -c 160 /tmp/whep_$c.json 2>/dev/null)"
  sleep 2
done

echo "=== after ==="
curl -sS http://127.0.0.1:8080/api/health | python3 -c 'import sys,json; h=json.load(sys.stdin); print("idle", h.get("preview_idle"))'
pgrep -af 'rpicam-vid' | head -6 || true
echo STABILIZE_DONE
