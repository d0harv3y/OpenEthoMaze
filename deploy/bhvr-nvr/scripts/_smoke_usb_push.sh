#!/bin/bash
set -euo pipefail
cd "$HOME/bhvr-kiosk"
echo '--- status ---'
curl -sS -m 45 http://127.0.0.1:8080/api/kiosk/status | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
print("soft", d.get("soft_present"), "/", d.get("soft_total"))
print("tree", d.get("cam_tree"))
miss = [f["rel"] for f in d.get("soft_files", []) if not f["present"]]
print("missing", miss)
print("eligible", [c["id"] for c in d.get("eligible", []) if c.get("eligible")])
'
CAM="${1:-bhvr-cam3}"
echo "--- push $CAM ---"
curl -sS -m 300 -X POST http://127.0.0.1:8080/api/kiosk/usb-push \
  -H 'Content-Type: application/json' \
  -d "{\"cam_ids\":[\"$CAM\"]}" | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
print("ok", d.get("ok"), "pushed", d.get("pushed"), "/", d.get("total"))
for r in d.get("results") or []:
    print(r.get("ok"), r.get("id"), r.get("ip"))
    for line in (r.get("log") or [])[-8:]:
        print(" ", line)
'
echo USB_PUSH_SMOKE_DONE
