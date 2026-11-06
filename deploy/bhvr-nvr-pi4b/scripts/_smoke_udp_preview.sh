#!/bin/bash
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15)
echo "=== cam procs ==="
ssh "${KEY[@]}" admin@192.168.7.27 'ps aux | grep -E "rpicam|ffmpeg" | grep -v grep || true; ls -la ~/bin/ffmpeg'
echo "=== health ==="
curl -s http://127.0.0.1:8080/api/health; echo
echo "=== preview 20s ==="
timeout 20 curl -N -sS -o /tmp/udp-prev3.bin -w "bytes=%{size_download} http=%{http_code}\n" \
  "http://127.0.0.1:8080/api/preview/bhvr-cam1" || true
ls -la /tmp/udp-prev3.bin 2>/dev/null || true
od -An -tx1 -N32 /tmp/udp-prev3.bin 2>/dev/null || true
echo "=== cam stderr ==="
tail -40 /tmp/bhvr-preview-bhvr-cam1-cam.log 2>/dev/null || true
echo "=== nvr stderr ==="
tail -20 /tmp/bhvr-preview-bhvr-cam1.log 2>/dev/null || true
