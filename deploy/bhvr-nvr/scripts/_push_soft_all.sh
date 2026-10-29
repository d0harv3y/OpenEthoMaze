#!/bin/bash
set -euo pipefail
cd "$HOME/bhvr-kiosk"
# Ensure latest push code
if [[ -f /tmp/bhvr-ks/kiosk_settings.py ]]; then
  cp -f /tmp/bhvr-ks/kiosk_settings.py app/kiosk_settings.py
fi
curl -sS -m 60 http://127.0.0.1:8080/api/kiosk/status | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
print("soft", d.get("soft_present"), "/", d.get("soft_total"))
print("tree", d.get("cam_tree"))
elig = [c["id"] for c in d.get("eligible", []) if c.get("eligible")]
print("eligible", elig)
open("/tmp/bhvr_push_ids.json","w").write(json.dumps({"cam_ids": elig}))
if not elig:
    raise SystemExit("no eligible USB cams")
'
echo "=== push ==="
curl -sS -m 900 -X POST http://127.0.0.1:8080/api/kiosk/usb-push \
  -H 'Content-Type: application/json' \
  -d @"/tmp/bhvr_push_ids.json" | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
print("ok", d.get("ok"), "pushed", d.get("pushed"), "/", d.get("total"))
for r in d.get("results") or []:
    print(("OK" if r.get("ok") else "FAIL"), r.get("id"), r.get("ip"))
    for line in (r.get("log") or [])[-4:]:
        print(" ", line)
'
echo PUSH_ALL_DONE
