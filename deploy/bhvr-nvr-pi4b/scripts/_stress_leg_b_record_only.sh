#!/bin/bash
# Stress leg B (issue 12): record-only soft 1920×1080 @ 30 ×4 (no live tiles).
# Stops WHEP, starts science session, samples NVR+cams, stops, prints fps.json.
set -euo pipefail

API=http://127.0.0.1:8080
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=/tmp/stress_leg_b_${STAMP}.txt
SAMPLE_S=${SAMPLE_S:-45}
CAMS_JSON='["bhvr-cam0","bhvr-cam1","bhvr-cam2","bhvr-cam3"]'
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)

log() { echo "$*" | tee -a "$OUT"; }
: >"$OUT"
log "stress leg B $STAMP soft=1080p@30 record-only sample=${SAMPLE_S}s"

# --- config: record soft 30 + 1080p profile available; sensor 1920:1080 ---
python3 - <<'PY' | tee -a "$OUT"
import os
from pathlib import Path
import yaml
p = Path.home() / "bhvr-kiosk" / "config.yaml"
cfg = yaml.safe_load(p.read_text()) or {}
rec = dict(cfg.get("record") or {})
rec["soft_fps"] = 30
rec["bitrate_kbps"] = max(int(rec.get("bitrate_kbps") or 2500), 4000)
cfg["record"] = rec
profs = list(cfg.get("profiles") or ["480p", "720p"])
if "1080p" not in profs:
    profs.append("1080p")
cfg["profiles"] = profs
cfg["cam_sensor_mode"] = {f"bhvr-cam{i}": "1920:1080" for i in range(4)}
# Keep preview at 1080p soft but we will stop live for this leg.
prev = dict(cfg.get("preview") or {})
prev.update({"width": 1920, "height": 1080, "fps_idle": 30, "sensor_mode": "1920:1080",
             "bitrate_kbps": max(int(prev.get("bitrate_kbps") or 2500), 4000)})
cfg["preview"] = prev
# SSD path in config may be unmounted; fall back to writable /data/bhvr for stress.
root = Path(str(cfg.get("data_root") or "/data/bhvr"))
if not root.parent.is_dir() or not os.access(str(root.parent), os.W_OK):
    print(f"WARN: data_root {root} not writable; using /data/bhvr")
    cfg["data_root"] = "/data/bhvr"
else:
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"WARN: cannot mkdir {root}: {exc}; using /data/bhvr")
        cfg["data_root"] = "/data/bhvr"
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
print("data_root", cfg.get("data_root"))
print("record", rec)
print("profiles", profs)
print("cam_sensor_mode", cfg["cam_sensor_mode"])
PY

# --- restart kiosk so PROFILE_GEOM 1080p + config load ---
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1
cd "$HOME/bhvr-kiosk"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >/tmp/kiosk-uvicorn.log 2>&1 &
for i in $(seq 1 15); do
  curl -sS -m 2 "$API/api/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -sS -m 5 "$API/api/health" | tee -a "$OUT"
echo >>"$OUT"

# --- stop any live + any prior session ---
curl -sS -m 15 -X POST "$API/api/preview/stop" >/dev/null || true
curl -sS -m 120 -X POST "$API/api/session/stop" >/dev/null || true
sleep 2

# --- start record session ---
log "=== session/start 1080p ×4 ==="
START=$(curl -sS -m 180 -w "\nHTTP:%{http_code}\n" -X POST "$API/api/session/start" \
  -H "Content-Type: application/json" \
  -d "{\"subject_id\":\"stress-leg-b\",\"sex\":\"U\",\"profile\":\"1080p\",\"protocol\":\"stress_leg_b\",\"notes\":\"issue12 leg B record-only\",\"camera_ids\":$CAMS_JSON}")
echo "$START" | tee -a "$OUT"
BODY=$(echo "$START" | sed '/^HTTP:/d')
FOLDER=$(python3 -c "import json,sys; s=sys.stdin.read().strip();
import re
s=re.sub(r'\nHTTP:\d+\s*$','',s)
d=json.loads(s) if s.startswith('{') else {};
print(d.get('folder') or '')" <<<"$BODY" 2>/dev/null || true)
log "folder=$FOLDER"
if [[ -z "$FOLDER" ]]; then
  log "FAIL: session/start did not return folder"
  tail -40 /tmp/kiosk-uvicorn.log | tee -a "$OUT" || true
  exit 1
fi
sleep 5
curl -sS -m 5 "$API/api/health" | tee -a "$OUT"
echo >>"$OUT"

sample_nvr() {
  {
    echo "--- NVR $(date -Is) ---"
    uptime
    echo "nproc=$(nproc)"
    free -h | head -2
    ps -eo pid,pcpu,pmem,rss,comm --sort=-pcpu | head -14
  } | tee -a "$OUT"
}

sample_nvr

# cam samples via roster IPs
mapfile -t ROWS < <(python3 - <<'PY'
import json, urllib.request
h = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=8))
for c in h.get("cameras") or []:
    print(f"{c['id']}\t{c['ip']}")
PY
)

for line in "${ROWS[@]}"; do
  cid=${line%%$'\t'*}
  ip=${line#*$'\t'}
  log "=== cam $cid @ $ip ==="
  ssh "${KEY[@]}" "admin@$ip" \
    'hostname; uptime; vcgencmd measure_temp 2>/dev/null; echo rpicam=$(pgrep -c rpicam-vid || echo 0); ps -eo pcpu,pmem,rss,comm,args | grep rpicam-vid | grep -v grep | head -3' \
    2>&1 | tee -a "$OUT" || log "WARN ssh $cid"
done

log "vmstat ${SAMPLE_S}s:"
vmstat 5 $((SAMPLE_S / 5 + 1)) | tee -a "$OUT"
sample_nvr

# h264 growth check
if [[ -n "$FOLDER" && -d "$FOLDER" ]]; then
  log "=== h264 sizes mid ==="
  ls -la "$FOLDER"/*.h264 2>/dev/null | tee -a "$OUT" || true
  sleep 10
  log "=== h264 sizes +10s ==="
  ls -la "$FOLDER"/*.h264 2>/dev/null | tee -a "$OUT" || true
fi

# --- stop session (writes fps.json from pts) ---
log "=== session/stop ==="
STOP=$(curl -sS -m 300 -X POST "$API/api/session/stop")
echo "$STOP" | tee -a "$OUT"

if [[ -n "$FOLDER" && -d "$FOLDER" ]]; then
  log "=== fps.json ==="
  for f in "$FOLDER"/*_fps.json; do
    [[ -f "$f" ]] || continue
    log "-- $f --"
    cat "$f" | tee -a "$OUT"
    echo >>"$OUT"
  done
  log "=== capture logs (tail) ==="
  for f in "$FOLDER"/*_capture.log; do
    [[ -f "$f" ]] || continue
    log "-- $f --"
    tail -15 "$f" | tee -a "$OUT"
  done
  log "=== final sizes ==="
  ls -la "$FOLDER" | tee -a "$OUT"
fi

log "final health:"
curl -sS -m 5 "$API/api/health" | tee -a "$OUT"
echo >>"$OUT"
log "DONE $OUT"
echo "$OUT"
