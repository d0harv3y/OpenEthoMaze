#!/bin/bash
# Quick NVR/cam state before ×4 live fan-out chase.
set -uo pipefail
echo "=== leftover ==="
pgrep -af "ffmpeg|nc -l|fanout|rpicam" | head -40 || true
echo "=== roster ==="
python3 - <<'PY'
import json, urllib.request
h = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=8))
for c in h.get("cameras") or []:
    print(c.get("id"), c.get("ip"), c.get("online"))
PY
echo "=== ssh cams ==="
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  if out=$(ssh "${KEY[@]}" "admin@$ip" "hostname" 2>/dev/null); then
    echo "UP $ip $out"
  else
    echo "DOWN $ip"
  fi
done
echo "=== mtx udp listeners ==="
ss -ulnp | grep -E "1555[0-3]" || true
echo "=== mediamtx paths ==="
grep -A20 "^paths:" ~/bhvr-mediamtx/mediamtx.yml | head -30
echo "=== load ==="
uptime
nproc
free -h | head -2
