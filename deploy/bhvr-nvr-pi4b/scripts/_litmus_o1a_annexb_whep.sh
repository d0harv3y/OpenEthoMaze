#!/bin/bash
# Litmus O1a: whep_ingest=nvr_annexb — cam has rpicam only; NVR remux; WHEP 204.
set -euo pipefail
API=http://127.0.0.1:8080
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)

python3 - <<'PY'
from pathlib import Path
import yaml
p = Path.home() / "bhvr-kiosk" / "config.yaml"
cfg = yaml.safe_load(p.read_text()) or {}
prev = dict(cfg.get("preview") or {})
prev["transport"] = "whep"
prev["whep_ingest"] = "nvr_annexb"
cfg["preview"] = prev
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
print("whep_ingest", prev["whep_ingest"])
PY

pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1
cd "$HOME/bhvr-kiosk"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >/tmp/kiosk-uvicorn.log 2>&1 &
for i in $(seq 1 15); do
  curl -sS -m 2 "$API/api/health" >/dev/null 2>&1 && break
  sleep 1
done

curl -sS -m 10 -X POST "$API/api/preview/stop" >/dev/null || true
sleep 1

for c in bhvr-cam0 bhvr-cam1; do
  echo "=== start $c ==="
  curl -sS -m 60 -X POST "$API/api/preview/$c/whep/start"
  echo
done

sleep 4
echo "=== health ==="
curl -sS "$API/api/health"; echo

echo "=== cam procs (want rpicam=1 ffmpeg=0 on cam) ==="
python3 - <<'PY'
import json, urllib.request, subprocess
h = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=8))
key = ["-i", __import__("os").path.expanduser("~/.ssh/id_ed25519_bhvr"),
       "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
       "-o", "StrictHostKeyChecking=accept-new"]
for c in h.get("cameras") or []:
    if c["id"] not in ("bhvr-cam0", "bhvr-cam1"):
        continue
    ip = c["ip"]
    out = subprocess.check_output(
        ["ssh", *key, f"admin@{ip}",
         "hostname; echo rpicam=$(pgrep -c rpicam-vid || echo 0); echo ffmpeg=$(pgrep -c ffmpeg || echo 0)"],
        text=True, stderr=subprocess.STDOUT,
    )
    print(c["id"], ip, out.strip().replace("\n", " | "))
PY

echo "=== remux on NVR ==="
pgrep -af "ffmpeg.*127.0.0.1:1555" || true
echo "=== whep OPTIONS ==="
for c in bhvr-cam0 bhvr-cam1; do
  code=$(curl -sS -m 5 -o /dev/null -w "%{http_code}" -X OPTIONS "http://127.0.0.1:8889/$c/whep")
  echo "$c $code"
done
echo "=== remux logs (tail) ==="
tail -5 /tmp/bhvr-preview-bhvr-cam0-remux.log 2>/dev/null || true
tail -5 /tmp/bhvr-preview-bhvr-cam1-remux.log 2>/dev/null || true
