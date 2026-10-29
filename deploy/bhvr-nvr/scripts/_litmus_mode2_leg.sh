#!/bin/bash
# Mode 2 A/B litmus helper (manual stopwatch). Run ON NVR.
#   LEG=A|B bash _litmus_mode2_leg.sh
# A = whep + nvr_annexb (SSH annex-B → MediaMTX → WHEP)
# B = mpegts (SSH MPEG-TS → browser mpegts.js)
#
# Objective A↔B auto (TTFF + wall_fps CSV, ×N cams):
#   bash _litmus_mode2_ab_auto.sh
set -euxo pipefail
LEG="${LEG:-A}"
KIOSK="${HOME}/bhvr-kiosk"
NVR_WLAN="${NVR_WLAN:-10.248.238.22}"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)

pick_cam() {
  python3 - <<'PY'
import json, subprocess, urllib.request
key = ["ssh", "-i", __import__("os").path.expanduser("~/.ssh/id_ed25519_bhvr"),
       "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6"]
cams = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=5))["cameras"]
# Prefer cam2, then any non-192.168.7 online
order = sorted(cams, key=lambda c: (0 if c.get("id") == "bhvr-cam2" else 1, c.get("id") or ""))
for c in order:
    if not c.get("online"):
        continue
    ip = str(c.get("ip") or "")
    if ip.startswith("192.168.7."):
        continue
    try:
        subprocess.check_call(key + [f"admin@{ip}", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        continue
    print(c["id"], ip)
    break
else:
    raise SystemExit("no WLAN cam with working SSH")
PY
}

read -r CAM_ID CAM_IP < <(pick_cam)
echo "LITMUS_CAM $CAM_ID $CAM_IP LEG=$LEG"

python3 - <<PY
from pathlib import Path
import yaml
p = Path.home() / "bhvr-kiosk" / "config.yaml"
cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
prev = cfg.get("preview") or {}
prev["nvr_host"] = "$NVR_WLAN"
prev["buffer_count"] = 2
if "$LEG" == "A":
    prev["transport"] = "whep"
    prev["whep_ingest"] = "nvr_annexb"
else:
    prev["transport"] = "mpegts"
cfg["preview"] = prev
# Prefer Lite defaults while Mode2 soak
cfg["default_profile"] = "lite"
rec = cfg.get("record") or {}
rec["soft_fps"] = 10
cfg["record"] = rec
p.write_text(yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False), encoding="utf-8")
print("patched", prev)
PY

# Hard restart uvicorn
pids=$(pgrep -f '[u]vicorn app.main' || true)
if [[ -n "${pids}" ]]; then kill -9 $pids || true; fi
sleep 1
cd "$KIOSK"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 3
curl -sS http://127.0.0.1:8080/api/health
echo

# Stop all previews then start litmus cam only (score one cam; others may still be in roster)
curl -sS -X POST http://127.0.0.1:8080/api/preview/stop >/dev/null || true
sleep 1

if [[ "$LEG" == "A" ]]; then
  curl -sS -X POST "http://127.0.0.1:8080/api/preview/${CAM_ID}/whep/start"
  echo
  echo "READY_LEG_A cam=$CAM_ID"
  echo "Operator: hard-refresh kiosk, tap LIVE on $CAM_ID only if needed."
  echo "Stopwatch: clap/LED in front of that cam; note glass-to-glass seconds + badge fps."
  echo "WHEP URL: http://127.0.0.1:8889/${CAM_ID}/whep (browser via kiosk)"
else
  echo "READY_LEG_B cam=$CAM_ID transport=mpegts"
  echo "Operator: hard-refresh kiosk, tap tile $CAM_ID to start SSH MPEG-TS live."
  echo "Stopwatch: same clap/LED; note seconds + badge fps."
fi
