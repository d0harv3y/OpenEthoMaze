#!/bin/bash
# Run ON NVR; SSHes to cam0. Compare rpicam knobs for soft 1080p30 pts fps.
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
CAM_IP=$(python3 - <<'PY'
import json, urllib.request
h = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=8))
for c in h.get("cameras") or []:
    if c.get("id") == "bhvr-cam0":
        print(c["ip"]); break
PY
)
echo "cam=$CAM_IP"
curl -sS -m 10 -X POST http://127.0.0.1:8080/api/preview/stop >/dev/null || true
sleep 1

# Push runner to cam
ssh "${KEY[@]}" "admin@${CAM_IP}" 'cat > /tmp/knob_matrix.sh && chmod +x /tmp/knob_matrix.sh' <<'EOS'
#!/bin/bash
set -euo pipefail
pkill -INT rpicam-vid 2>/dev/null || true
sleep 0.5

run() {
  local tag="$1"; shift
  rm -f "/tmp/${tag}.h264" "/tmp/${tag}.pts"
  echo "=== $tag: $* ==="
  rpicam-vid -n -t 8000 "$@" --save-pts "/tmp/${tag}.pts" -o "/tmp/${tag}.h264"
  python3 - "$tag" <<'PY'
import sys
from pathlib import Path
tag = sys.argv[1]
pts = Path(f"/tmp/{tag}.pts")
h264 = Path(f"/tmp/{tag}.h264")
vals = []
for ln in pts.read_text().splitlines() if pts.exists() else []:
    ln = ln.strip()
    if not ln or ln.startswith("#"):
        continue
    p = ln.replace(",", " ").split()
    try:
        vals.append(float(p[1] if len(p) >= 2 else p[0]))
    except Exception:
        pass
n = len(vals)
fps = None
if n >= 2:
    span = vals[-1] - vals[0]
    fps = (n - 1) / (span / 1000.0)
print(f"{tag}: bytes={h264.stat().st_size if h264.exists() else 0} pts_n={n} fps={fps}")
PY
}

BASE=(--mode 1920:1080:10:P --width 1920 --height 1080 --framerate 30 --codec h264 --inline --intra 30 --bitrate 4000000 --denoise cdn_off)

run D2 "${BASE[@]}" --buffer-count 4
run F  "${BASE[@]}" --buffer-count 4 --flush
run G  "${BASE[@]}" --buffer-count 2 --flush
run H  "${BASE[@]}" --buffer-count 6 --flush
run I  --width 1920 --height 1080 --framerate 30 --codec h264 --inline --intra 30 --bitrate 4000000 --denoise cdn_off --buffer-count 4 --flush
EOS

ssh "${KEY[@]}" "admin@${CAM_IP}" 'bash /tmp/knob_matrix.sh'
