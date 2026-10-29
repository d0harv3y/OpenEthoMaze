#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)
bash /tmp/_snap_roster.sh 2>/dev/null || true
curl -sS -m 3 http://127.0.0.1:8080/api/health | head -c 200; echo
for ip in 10.248.235.74 192.168.7.28; do
  echo "=== free $ip ==="
  ssh "${KEY[@]}" "admin@$ip" \
    'pkill -9 rpicam-vid 2>/dev/null||true; pkill -9 -x ffmpeg 2>/dev/null||true; hostname; pgrep -a rpicam||echo no_rpicam' \
    2>&1 | head -10 || echo SSH_FAIL
done
echo "=== whep/start cam3 ==="
curl -sS -m 90 -X POST "http://127.0.0.1:8080/api/preview/bhvr-cam3/whep/start" \
  -w "\nHTTP %{http_code}\n" | tail -20
