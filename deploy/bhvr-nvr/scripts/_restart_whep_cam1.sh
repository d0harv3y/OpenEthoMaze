#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10)
CAM=admin@192.168.7.27

echo '=== whep/start ==='
curl -sS -m 45 -X POST http://127.0.0.1:8080/api/preview/bhvr-cam1/whep/start || true
echo
sleep 3
echo '=== cam publishers ==='
ssh "${KEY[@]}" "$CAM" 'pgrep -a rpicam-vid || echo no_rpicam; pgrep -a ffmpeg || echo no_ffmpeg; echo ---; ls -la /tmp/bhvr-preview-bhvr-cam1-cam.log 2>/dev/null; tail -40 /tmp/bhvr-preview-bhvr-cam1-cam.log 2>/dev/null || tail -40 /tmp/live_udp.log 2>/dev/null || true'
echo '=== nvr preview log ==='
tail -40 /tmp/bhvr-preview-bhvr-cam1-cam.log 2>/dev/null || true
ls /tmp/bhvr-preview* 2>/dev/null || true
echo '=== whep options ==='
curl -sS -m 5 -o /dev/null -w 'whep=%{http_code}\n' -X OPTIONS http://127.0.0.1:8889/bhvr-cam1/whep || true
