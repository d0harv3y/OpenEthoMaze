#!/bin/bash
set -euxo pipefail
curl -sS -X POST http://127.0.0.1:8080/api/preview/stop || true
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10)
ssh "${KEY[@]}" admin@10.248.229.141 'pkill -9 rpicam-vid 2>/dev/null || true; pkill -9 -f "[f]fmpeg" 2>/dev/null || true; sleep 1; pgrep rpicam-vid || echo CAM_CLEAR'
sleep 2
bash /tmp/_probe_ssh_mpegts_bytes.sh
echo "=== API pull ==="
curl -sS -o /tmp/legb3.ts -w "HTTP %{http_code} bytes=%{size_download}\n" --max-time 12 \
  "http://127.0.0.1:8080/api/preview/bhvr-cam2?t=legb3" || true
ls -la /tmp/legb3.ts || true
