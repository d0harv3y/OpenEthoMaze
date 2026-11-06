#!/bin/bash
# Find cam0 and why preview fails
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)

echo '=== kiosk cams / config ==='
python3 - <<'PY'
from pathlib import Path
import json, yaml
cfg = yaml.safe_load(Path.home().joinpath("bhvr-kiosk/config.yaml").read_text()) or {}
print("preview:", cfg.get("preview"))
print("cam_sensor_mode:", cfg.get("cam_sensor_mode"))
for p in [
  Path("/tmp/bhvr-preview-bhvr-cam0-cam.log"),
  Path("/tmp/bhvr-preview-bhvr-cam0.log"),
  Path.home()/"bhvr-kiosk"/"roster.json",
]:
  if p.exists():
    print(f"--- {p} ({p.stat().st_size}b) ---")
    print(p.read_text()[-2000:])
PY

echo '=== try common APIs ==='
for u in \
  http://127.0.0.1:8080/api/cams \
  http://127.0.0.1:8080/api/status \
  http://127.0.0.1:8080/api/health
do
  code=$(curl -sS -m 3 -o /tmp/api.out -w '%{http_code}' "$u" || echo fail)
  echo "$code $u"
  head -c 400 /tmp/api.out 2>/dev/null; echo
done

echo '=== usb neighbors ==='
ip -4 -br a | grep -E 'usb|192.168.7' || true
# probe .2-.40 for bhvr-cam0
for i in $(seq 2 40); do
  ip=192.168.7.$i
  if ping -c1 -W1 "$ip" >/dev/null 2>&1; then
    h=$(ssh "${KEY[@]}" admin@"$ip" 'hostname' 2>/dev/null || echo '?')
    echo "up $ip hostname=$h"
  fi
done

echo '=== mediamtx paths ==='
curl -sS -m 3 http://127.0.0.1:9997/v3/paths/list 2>/dev/null | head -c 1500 || true
echo
tail -30 /tmp/mediamtx.log 2>/dev/null | grep -i cam0 || true
