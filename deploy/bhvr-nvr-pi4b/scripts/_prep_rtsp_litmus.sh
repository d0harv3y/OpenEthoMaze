#!/bin/bash
# Prep MediaMTX for native RTSP litmus: enable rtsp, clear orphan, wait for healthy unit.
set -euo pipefail
YML="${HOME}/bhvr-mediamtx/mediamtx.yml"

python3 - "$YML" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text()
if "rtsp: false" in text:
    text = text.replace("rtsp: false", "rtsp: true", 1)
if "rtspAddress:" not in text:
    text = text.replace("rtsp: true", "rtsp: true\nrtspAddress: :8554", 1)
p.write_text(text)
print("rtsp lines:", [l for l in text.splitlines() if l.startswith("rtsp")])
PY

echo "=== kill orphan mediamtx (not under healthy systemd) ==="
# Kill any mediamtx holding ports; systemd should respawn with new yml.
pkill -x mediamtx || true
sleep 3

echo "=== status ==="
pgrep -af '/bhvr-mediamtx/mediamtx' || echo "no mediamtx yet"
ss -tlnp | grep -E '8889|8554' || true
systemctl is-active bhvr-mediamtx || true
journalctl -u bhvr-mediamtx -n 20 --no-pager || true
