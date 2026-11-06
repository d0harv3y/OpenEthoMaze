#!/bin/bash
# Quick diag: why kiosk live badge says fail
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10)
CAM=admin@192.168.7.27

echo '=== NVR MediaMTX / kiosk ==='
pgrep -a mediamtx || echo 'no_mediamtx'
ss -ulnp 2>/dev/null | grep -E '15550|8889|8554' || netstat -ulnp 2>/dev/null | grep -E '15550|8889' || true
python3 - <<'PY'
from pathlib import Path
import yaml
for p in [Path.home()/"bhvr-kiosk/config.yaml", Path.home()/"bhvr-kiosk/config.yml"]:
  if p.exists():
    c=yaml.safe_load(p.read_text()) or {}
    prev=(c.get("preview") or {})
    print(f"config={p}")
    print(f"transport={prev.get('transport')}")
    print(f"width={prev.get('width')} height={prev.get('height')} fps={prev.get('fps')}")
    print(f"nvr_host={prev.get('nvr_host')} mediamtx_http={prev.get('mediamtx_http')}")
    break
else:
  print("no_kiosk_config")
PY
curl -sS -m 3 -o /dev/null -w 'whep_options=%{http_code}\n' -X OPTIONS http://127.0.0.1:8889/bhvr-cam1/whep || echo whep_unreachable
curl -sS -m 3 http://127.0.0.1:8080/api/roster 2>/dev/null | head -c 800 || echo roster_fail
echo
echo '=== cam1 ==='
ssh "${KEY[@]}" "$CAM" 'hostname; command -v ffmpeg; command -v rpicam-vid; ls -la ~/bin/ffmpeg 2>/dev/null; dpkg -l ffmpeg rpicam-apps 2>/dev/null | tail -5; echo ---; pgrep -a rpicam-vid || echo no_rpicam; pgrep -a ffmpeg || echo no_ffmpeg; echo ---; tail -25 /tmp/live_udp.log 2>/dev/null || echo no_live_log; echo ---; dpkg --audit 2>/dev/null | head -30 || true'
