#!/bin/bash
# Install Kiosk-settings NVR sudoers + soft-push to all ONLINE·USB cams.
set -euo pipefail
SUDOERS_SRC="${HOME}/deploy/bhvr-nvr/sudoers/bhvr-nvr-kiosk"
if [[ ! -f "$SUDOERS_SRC" ]]; then
  # staged from laptop
  SUDOERS_SRC="/tmp/bhvr-ks/bhvr-nvr-kiosk"
fi
test -f "$SUDOERS_SRC"
echo "=== sudoers ==="
if sudo -n true 2>/dev/null; then
  sudo -n install -m 440 "$SUDOERS_SRC" /etc/sudoers.d/bhvr-nvr-kiosk
  sudo -n visudo -cf /etc/sudoers.d/bhvr-nvr-kiosk
  echo sudoers_ok
else
  echo "NEED_PASSWORD: run once:"
  echo "  sudo install -m 440 $SUDOERS_SRC /etc/sudoers.d/bhvr-nvr-kiosk"
  echo "  sudo visudo -cf /etc/sudoers.d/bhvr-nvr-kiosk"
fi
# Probe scoped cmds
for cmd in "nmcli -t -f NAME connection show" "mkdir -p /tmp/bhvr-sudoers-probe" "true"; do
  if sudo -n $cmd >/dev/null 2>&1; then
    echo "sudo_ok: $cmd"
  else
    echo "sudo_fail: $cmd"
  fi
done
rmdir /tmp/bhvr-sudoers-probe 2>/dev/null || true

echo "=== soft push all eligible ==="
cd "$HOME/bhvr-kiosk"
curl -sS -m 45 http://127.0.0.1:8080/api/kiosk/status | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
elig = [c["id"] for c in d.get("eligible", []) if c.get("eligible")]
print("eligible", elig)
open("/tmp/bhvr_push_ids.json","w").write(json.dumps({"cam_ids": elig}))
'
IDS=$(cat /tmp/bhvr_push_ids.json)
echo "POST $IDS"
curl -sS -m 600 -X POST http://127.0.0.1:8080/api/kiosk/usb-push \
  -H 'Content-Type: application/json' \
  -d "$IDS" | .venv/bin/python -c '
import sys, json
d = json.load(sys.stdin)
print("ok", d.get("ok"), "pushed", d.get("pushed"), "/", d.get("total"))
for r in d.get("results") or []:
    print(("OK" if r.get("ok") else "FAIL"), r.get("id"), r.get("ip"))
    for line in (r.get("log") or [])[-3:]:
        print(" ", line)
'
echo ALL_DONE
