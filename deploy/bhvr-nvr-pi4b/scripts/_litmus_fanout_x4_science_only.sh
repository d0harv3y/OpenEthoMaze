#!/bin/bash
# Prove 4× concurrent science annex-B over TCP hits pts>=25 with NO live scale.
set -euo pipefail
API=http://127.0.0.1:8080
CAMS=(bhvr-cam0 bhvr-cam1 bhvr-cam2 bhvr-cam3)
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
DUR_ENCODE="${DUR_ENCODE:-20}"
SUMMARY=/tmp/fanout_sci_only.txt
: >"$SUMMARY"
log() { echo "$*" | tee -a "$SUMMARY"; }
ord_of() { echo "${1#bhvr-cam}"; }

curl -sS -m 10 -X POST "$API/api/preview/stop" >/dev/null || true
sleep 1
pkill -f "nc -l -p 1656" 2>/dev/null || true

declare -A CAM_IP=()
while IFS=$'\t' read -r cid ip; do
  CAM_IP[$cid]=$ip
done < <(python3 - <<'PY'
import json, urllib.request
h = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=8))
for c in h.get("cameras") or []:
    if c.get("id") and c.get("ip"):
        print(f"{c['id']}\t{c['ip']}")
PY
)

ACTIVE=()
log "=== science-only ×4 $(date -Is) encode=${DUR_ENCODE}s ==="
for c in "${CAMS[@]}"; do
  n=$(ord_of "$c")
  ip=${CAM_IP[$c]:-}
  tcp=$((16560 + n))
  [[ -n "$ip" ]] || continue
  if ! ssh "${KEY[@]}" "admin@$ip" 'echo ok' >/dev/null 2>&1; then
    log "SKIP $c SSH"; continue
  fi
  ACTIVE+=("$c")
  rm -f "/tmp/fanout_${c}_science.h264" "/tmp/fanout_${c}.pts"
  ssh "${KEY[@]}" "admin@$ip" 'pkill -INT rpicam-vid 2>/dev/null || true; pkill -x nc 2>/dev/null || true' || true
  nc -l -p "$tcp" >"/tmp/fanout_${c}_science.h264" &
  echo $! >"/tmp/fanout_${c}_sci.pid"
  ssh "${KEY[@]}" "admin@$ip" "cat > /tmp/fanout_sci.sh && chmod +x /tmp/fanout_sci.sh" <<EOS
#!/bin/bash
pkill -INT rpicam-vid 2>/dev/null || true
pkill -x nc 2>/dev/null || true
sleep 0.2
rm -f /tmp/fanout.pts
exec stdbuf -o0 rpicam-vid -n -t $((DUR_ENCODE * 1000)) --mode 1920:1080:10:P \
  --width 1920 --height 1080 --framerate 30 --codec h264 --inline \
  --intra 30 --flush --bitrate 4000000 --denoise cdn_off --buffer-count 6 \
  --save-pts /tmp/fanout.pts -o - \
| /usr/bin/nc -N 192.168.7.1 ${tcp}
EOS
  ssh "${KEY[@]}" "admin@$ip" 'nohup /tmp/fanout_sci.sh >/tmp/fanout_sci.log 2>&1 &' || true
  log "started $c → :$tcp"
done
log "active ${ACTIVE[*]}"
sleep $((DUR_ENCODE + 5))

for c in "${ACTIVE[@]}"; do
  ip=${CAM_IP[$c]}
  ssh "${KEY[@]}" "admin@$ip" 'pkill -INT rpicam-vid 2>/dev/null || true; pkill -x nc 2>/dev/null || true; sleep 0.3; cat /tmp/fanout.pts' \
    >"/tmp/fanout_${c}.pts" 2>/dev/null || true
  [[ -f "/tmp/fanout_${c}_sci.pid" ]] && kill "$(cat "/tmp/fanout_${c}_sci.pid")" 2>/dev/null || true
done
pkill -f "nc -l -p 1656" 2>/dev/null || true

pass=0
fail=0
for c in "${ACTIVE[@]}"; do
  python3 - "$c" <<'PY' | tee -a "$SUMMARY"
import sys
from pathlib import Path
cam = sys.argv[1]
vals = []
for ln in Path(f"/tmp/fanout_{cam}.pts").read_text().splitlines() if Path(f"/tmp/fanout_{cam}.pts").exists() else []:
    ln = ln.strip()
    if not ln or ln.startswith("#"):
        continue
    p = ln.replace(",", " ").split()
    try:
        vals.append(float(p[1] if len(p) >= 2 else p[0]))
    except Exception:
        pass
n = len(vals)
fps = (n - 1) / ((vals[-1] - vals[0]) / 1000.0) if n >= 2 else None
b = Path(f"/tmp/fanout_{cam}_science.h264").stat().st_size if Path(f"/tmp/fanout_{cam}_science.h264").exists() else 0
ok = (fps or 0) >= 25
print(f"science {cam} bytes={b} pts_n={n} pts_fps={fps} {'PASS' if ok else 'FAIL'}")
PY
done
log "DONE $SUMMARY"
