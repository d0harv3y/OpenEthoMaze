#!/bin/bash
# Stress leg A (issue 12): soft 1920×1080 @ 30 live ×4 via WHEP.
# Mutates ~/bhvr-kiosk/config.yaml, restarts publishes, samples cam + NVR load.
set -euo pipefail

API=http://127.0.0.1:8080
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=/tmp/stress_leg_a_${STAMP}.txt
SAMPLE_S=${SAMPLE_S:-40}
CAMS=(bhvr-cam0 bhvr-cam1 bhvr-cam2 bhvr-cam3)

log() { echo "$*" | tee -a "$OUT"; }

: >"$OUT"
log "stress leg A $STAMP soft=1920x1080@30 sample=${SAMPLE_S}s"

# --- mutate config ---
python3 - <<'PY' | tee -a "$OUT"
from pathlib import Path
import yaml
p = Path.home() / "bhvr-kiosk" / "config.yaml"
cfg = yaml.safe_load(p.read_text()) or {}
prev = dict(cfg.get("preview") or {})
prev.update({
    "width": 1920,
    "height": 1080,
    "fps_idle": 30,
    "bitrate_kbps": max(int(prev.get("bitrate_kbps") or 2500), 4000),
    # OV5647 1080p30 + --flush needs ≥4; prefer 6 (buf=2 halves pts ~15).
    "buffer_count": max(int(prev.get("buffer_count") or 6), 6),
    "sensor_mode": "1920:1080",
})
# Keep current whep ingest (nvr_annexb / cam_mpegts); do not force.
cfg["preview"] = prev
cfg["cam_sensor_mode"] = {f"bhvr-cam{i}": "1920:1080" for i in range(4)}
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
print("preview", prev)
print("cam_sensor_mode", cfg["cam_sensor_mode"])
PY

# --- restart kiosk ---
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1
cd "$HOME/bhvr-kiosk"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >/tmp/kiosk-uvicorn.log 2>&1 &
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sS -m 2 "$API/api/health" >/tmp/kiosk_health.json 2>/dev/null; then
    cat /tmp/kiosk_health.json | tee -a "$OUT"
    echo >>"$OUT"
    break
  fi
  sleep 1
done
if ! curl -sS -m 2 "$API/api/health" >/dev/null 2>&1; then
  log "FAIL: kiosk did not come up"
  tail -30 /tmp/kiosk-uvicorn.log | tee -a "$OUT" || true
  exit 1
fi

# --- cam id → ip from health/roster ---
mapfile -t ROSTER < <(python3 - <<'PY'
import json, urllib.request
for url in (
    "http://127.0.0.1:8080/api/cams",
    "http://127.0.0.1:8080/api/roster",
    "http://127.0.0.1:8080/api/status",
):
    try:
        h = json.load(urllib.request.urlopen(url, timeout=5))
    except Exception:
        continue
    cams = []
    if isinstance(h, list):
        cams = h
    elif isinstance(h, dict):
        cams = h.get("cameras") or h.get("cams") or h.get("roster") or []
        if not cams and "preview_idle" in h:
            continue
    for c in cams:
        if not isinstance(c, dict):
            continue
        cid = c.get("id") or c.get("cam_id") or c.get("hostname") or c.get("name")
        ip = c.get("ip") or c.get("addr") or c.get("host") or c.get("ipv4")
        if cid and ip:
            print(f"{cid}\t{ip}")
    if cams:
        break
PY
)

declare -A CAM_IP=()
for line in "${ROSTER[@]:-}"; do
  cid=${line%%$'\t'*}
  ip=${line#*$'\t'}
  [[ -n "$cid" && -n "$ip" && "$cid" != "$ip" ]] || continue
  CAM_IP[$cid]=$ip
  log "roster $cid → $ip"
done
# USB fallbacks if roster incomplete
CAM_IP[bhvr-cam0]=${CAM_IP[bhvr-cam0]:-192.168.7.41}
CAM_IP[bhvr-cam1]=${CAM_IP[bhvr-cam1]:-192.168.7.27}
CAM_IP[bhvr-cam2]=${CAM_IP[bhvr-cam2]:-192.168.7.31}
CAM_IP[bhvr-cam3]=${CAM_IP[bhvr-cam3]:-192.168.7.28}
for c in "${CAMS[@]}"; do log "use $c → ${CAM_IP[$c]}"; done

# --- start 4× WHEP ---
curl -sS -m 10 -X POST "$API/api/preview/stop" >/dev/null || true
sleep 1
for c in "${CAMS[@]}"; do
  log "=== whep/start $c ==="
  curl -sS -m 75 -X POST "$API/api/preview/$c/whep/start" | tee -a "$OUT" || true
  echo >>"$OUT"
done
sleep 5
log "health after start:"
curl -sS -m 5 "$API/api/health" | tee -a "$OUT"
echo >>"$OUT"

sample_nvr() {
  {
    echo "--- NVR $(date -Is) ---"
    uptime
    echo "nproc=$(nproc)"
    free -h | head -2
    ps -eo pid,pcpu,pmem,rss,comm --sort=-pcpu | head -12
    ss -ulnp | grep -E "1555[0-3]" || true
  } | tee -a "$OUT"
}

sample_nvr
sleep 8

# --- per-cam sample ---
for c in "${CAMS[@]}"; do
  ip=${CAM_IP[$c]}
  log "=== cam sample $c @ $ip ==="
  ssh "${KEY[@]}" "admin@$ip" 'hostname; uptime; vcgencmd measure_temp 2>/dev/null; echo rpicam=$(pgrep -c rpicam-vid 2>/dev/null || echo 0); echo ffmpeg=$(pgrep -c ffmpeg 2>/dev/null || echo 0); ps -eo pcpu,pmem,rss,comm,args | grep -E "rpicam-vid|ffmpeg" | grep -v grep | head -6' \
    2>&1 | tee -a "$OUT" || log "WARN: ssh $c failed"
done

# Non-destructive ingest rate: RTSP -c copy off MediaMTX while all 4 live.
log "=== RTSP copy fps (ingest, ${COPY_S:-8}s each) ==="
COPY_S=${COPY_S:-8}
for c in "${CAMS[@]}"; do
  clog=/tmp/stress_leg_a_copy_${c}.log
  timeout "$COPY_S" ffmpeg -hide_banner -loglevel info -rtsp_transport tcp \
    -i "rtsp://127.0.0.1:8554/${c}" -c copy -f null - 2>"$clog" || true
  python3 - "$c" "$clog" "$COPY_S" <<'PY' | tee -a "$OUT"
import re, sys
from pathlib import Path
cam, path, dur = sys.argv[1], Path(sys.argv[2]), float(sys.argv[3])
t = path.read_text(errors="replace") if path.exists() else ""
fr = re.findall(r"frame=\s*(\d+)", t)
fps = re.findall(r"fps=\s*([0-9.]+)", t)
sp = re.findall(r"speed=\s*([0-9.]+)x", t)
if fr:
    wall = int(fr[-1]) / dur
    print(f"{cam}: last_frame={fr[-1]} wall_fps={wall:.2f} fps_tail={fps[-4:] if fps else None} speed_tail={sp[-3:] if sp else None}")
else:
    print(f"{cam}: FAIL no frames (rtsp down?)")
PY
done

# Cam-side pts while live: SSH --save-pts is same encode; read via brief dig on cam
# by asking rpicam cmdline includes buffer-count (sanity).
for c in "${CAMS[@]}"; do
  ip=${CAM_IP[$c]}
  log "=== cmdline $c ==="
  ssh "${KEY[@]}" "admin@$ip" 'tr "\0" " " </proc/$(pgrep -n rpicam-vid)/cmdline 2>/dev/null | fold -s -w 120; echo' \
    2>&1 | tee -a "$OUT" || true
done

log "vmstat ${SAMPLE_S}s:"
vmstat 5 $((SAMPLE_S / 5 + 1)) | tee -a "$OUT"

sample_nvr
log "final health:"
curl -sS -m 5 "$API/api/health" | tee -a "$OUT"
echo >>"$OUT"

# quick pts check: stop one cam briefly? Better — SSH and parse rpicam stderr isn't pts.
# Run parallel 6s pts dig ONLY if STRESS_PTS=1 (kills live on that cam).
if [[ "${STRESS_PTS:-0}" == "1" ]]; then
  for c in bhvr-cam0 bhvr-cam1; do
    ip=${CAM_IP[$c]}
    log "=== pts dig $c (destroys that live briefly) ==="
    curl -sS -m 10 -X POST "$API/api/preview/stop?cam_id=$c" >/dev/null || true
    sleep 1
    ssh "${KEY[@]}" "admin@$ip" bash -s <<'EOS' 2>&1 | tee -a "$OUT" || true
pkill -INT rpicam-vid 2>/dev/null || true
sleep 0.3
# 6s capture; count frames via ffprobe if present
timeout 8 ~/bin/ffmpeg -hide_banner -loglevel info -f h264 -i pipe:0 -f null - \
  < <(timeout 6 rpicam-vid -n -t 6000 --mode 1920:1080:10:P --width 1920 --height 1080 \
      --framerate 30 --codec h264 --inline --bitrate 4000000 -o - 2>/tmp/rpicam_pts.err) \
  2>/tmp/ff_pts.err || true
grep -E "frame=|fps=" /tmp/ff_pts.err | tail -5 || true
tail -15 /tmp/rpicam_pts.err || true
EOS
    curl -sS -m 60 -X POST "$API/api/preview/$c/whep/start" | tee -a "$OUT" || true
    echo >>"$OUT"
  done
fi

log "DONE $OUT"
echo "$OUT"
