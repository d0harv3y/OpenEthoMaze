#!/bin/bash
set -euo pipefail
echo "=== health ==="
curl -sS http://127.0.0.1:8080/api/health; echo
echo "=== cams ==="
python3 - <<'PY'
import json, urllib.request
h = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=8))
for c in h.get("cameras") or []:
    print(c.get("id"), c.get("ip"), "online", c.get("online"), "age_s", c.get("age_s"))
PY
echo "=== whep OPTIONS ==="
for c in 0 1 2 3; do
  code=$(curl -sS -m 3 -o /dev/null -w "%{http_code}" -X OPTIONS "http://127.0.0.1:8889/bhvr-cam${c}/whep" || echo fail)
  echo "bhvr-cam${c} $code"
done
echo "=== remux / ports ==="
pgrep -af "ffmpeg.*127.0.0.1:1555" || true
ss -ulnp | grep 1555 || true
echo "=== brief RTSP wall_fps 5s ==="
for c in bhvr-cam0 bhvr-cam1 bhvr-cam2 bhvr-cam3; do
  timeout 5 ffmpeg -hide_banner -loglevel info -rtsp_transport tcp \
    -i "rtsp://127.0.0.1:8554/${c}" -c copy -f null - 2>/tmp/snap_${c}.log || true
  python3 - "$c" <<'PY'
import re, sys
from pathlib import Path
cam = sys.argv[1]
t = Path(f"/tmp/snap_{cam}.log").read_text(errors="replace")
fr = re.findall(r"frame=\s*(\d+)", t)
if fr:
    print(f"{cam} wall_fps={int(fr[-1])/5:.1f} frames={fr[-1]}")
else:
    print(f"{cam} FAIL")
PY
done
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=6)
echo "=== cam SSH ping ==="
python3 - <<'PY'
import json, urllib.request, subprocess, os
h = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=8))
key = ["-i", os.path.expanduser("~/.ssh/id_ed25519_bhvr"),
       "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6"]
for c in h.get("cameras") or []:
    cid, ip = c.get("id"), c.get("ip")
    if not cid or not ip:
        continue
    try:
        out = subprocess.check_output(
            ["ssh", *key, f"admin@{ip}",
             "echo ok; echo rpicam=$(pgrep -c rpicam-vid || echo 0); "
             "tr '\\0' ' ' </proc/$(pgrep -n rpicam-vid)/cmdline 2>/dev/null | grep -o 'buffer-count [0-9]*' || true"],
            text=True, stderr=subprocess.STDOUT, timeout=10,
        )
        print(cid, ip, out.strip().replace("\n", " | "))
    except Exception as e:
        print(cid, ip, "SSH_FAIL", type(e).__name__)
PY
