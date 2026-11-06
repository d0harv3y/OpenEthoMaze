#!/bin/bash
# ×4 fan-out: cam annex-B TCP → NVR.
# Stage A (no decode): TCP → science .h264 + localhost MPEG-TS raw (genpts)
# Stage B (may drop): raw UDP → scale/fps → MediaMTX
# Cams run until killed (-t 0); litmus stops them after live+science collect.
set -euo pipefail

API="${API:-http://127.0.0.1:8080}"
# Start flaky high ordinals first so they get a clean TCP accept before NVR load rises.
CAMS=(bhvr-cam3 bhvr-cam2 bhvr-cam1 bhvr-cam0)
DUR="${DURATION_S:-8}"
LIVE_W="${LIVE_W:-480}"
LIVE_H="${LIVE_H:-270}"
LIVE_FPS="${LIVE_FPS:-8}"
PASS_SCI="${PASS_SCI:-25}"
PASS_LIVE="${PASS_LIVE:-6}"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
SUMMARY=/tmp/fanout_x4_summary.txt
: >"$SUMMARY"
log() { echo "$*" | tee -a "$SUMMARY"; }
ord_of() { echo "${1#bhvr-cam}"; }

cleanup_nvr() {
  pkill -f "nc -l -p 1656" 2>/dev/null || true
  pkill -f "ffmpeg.*fanout_.*_science" 2>/dev/null || true
  pkill -f "ffmpeg.*udp://0.0.0.0:1567" 2>/dev/null || true
  pkill -f "fanout_scale_" 2>/dev/null || true
  for n in 0 1 2 3; do
    fuser -k "$((16560 + n))/tcp" 2>/dev/null || true
  done
}

curl -sS -m 10 -X POST "$API/api/preview/stop" >/dev/null || true
sleep 1
cleanup_nvr
sleep 1
# Do not restart MediaMTX mid-litmus (drops live paths). Warn only if binds missing.
n_mtx=0
for p in 15550 15551 15552 15553; do
  ss -uln 2>/dev/null | grep -q ":${p} " && n_mtx=$((n_mtx + 1))
done
log "MediaMTX binds ${n_mtx}/4 on 15550-15553 (pid=$(pgrep -x mediamtx || echo none))"
if [[ "$n_mtx" -lt 4 ]]; then
  log "WARN: incomplete MediaMTX binds — run _ensure_mediamtx_ports.sh before litmus"
fi

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
log "=== fan-out ×4 decoupled live=${LIVE_W}x${LIVE_H}@${LIVE_FPS} $(date -Is) ==="
for c in "${CAMS[@]}"; do
  n=$(ord_of "$c")
  ip=${CAM_IP[$c]:-}
  tcp=$((16560 + n))
  raw=$((15670 + n))
  mtx=$((15550 + n))
  [[ -n "$ip" ]] || continue
  if ! ssh "${KEY[@]}" "admin@$ip" 'echo ok' >/dev/null 2>&1; then
    log "SKIP $c SSH"; continue
  fi
  ACTIVE+=("$c")
  rm -f "/tmp/fanout_${c}_science.h264" "/tmp/fanout_${c}.pts" \
        "/tmp/fanout_${c}_ingest.log" "/tmp/fanout_${c}_scale.log"

  ssh "${KEY[@]}" "admin@$ip" 'pkill -INT rpicam-vid 2>/dev/null || true; pkill -x nc 2>/dev/null || true' || true

  # Stage A: bitstream copy only — science file + raw MPEG-TS (genpts for scale)
  nc -l -p "$tcp" | ffmpeg -hide_banner -loglevel warning -nostats \
    -thread_queue_size 2048 \
    -fflags +genpts+nobuffer+flush_packets -flags low_delay \
    -use_wallclock_as_timestamps 1 \
    -probesize 1000000 -analyzeduration 500000 \
    -f h264 -i pipe:0 \
    -map 0:v -c:v copy -f h264 "/tmp/fanout_${c}_science.h264" \
    -map 0:v -c:v copy -muxdelay 0 -muxpreload 0 \
      -mpegts_flags +resend_headers \
      -f mpegts "udp://127.0.0.1:${raw}?pkt_size=1316&overrun_nonfatal=1" \
    >"/tmp/fanout_${c}_ingest.log" 2>&1 &
  echo $! >"/tmp/fanout_${c}_ingest.pid"

  # Stage B: independent scale; UDP overrun drops under CPU pressure
  cat >"/tmp/fanout_scale_${c}.sh" <<SCE
#!/bin/bash
RAW=$raw
MTX=$mtx
LOG=/tmp/fanout_${c}_scale.log
: >"\$LOG"
while true; do
  echo "\$(date -Is) scale restart ${c} raw=\$RAW mtx=\$MTX" >>"\$LOG"
  ffmpeg -hide_banner -loglevel warning -nostats \
    -fflags +genpts+igndts+nobuffer+discardcorrupt -flags low_delay \
    -analyzeduration 2000000 -probesize 2000000 \
    -thread_queue_size 512 \
    -f mpegts -i "udp://0.0.0.0:\${RAW}?reuse=1&fifo_size=1000000&overrun_nonfatal=1" \
    -vf "scale=${LIVE_W}:${LIVE_H},fps=${LIVE_FPS}" \
    -c:v libx264 -preset ultrafast -tune zerolatency -g ${LIVE_FPS} -threads 1 \
    -an -f mpegts "udp://127.0.0.1:\${MTX}?pkt_size=1316&overrun_nonfatal=1" \
    >>"\$LOG" 2>&1 || true
  sleep 0.5
done
SCE
  chmod +x "/tmp/fanout_scale_${c}.sh"
  nohup "/tmp/fanout_scale_${c}.sh" >/dev/null 2>&1 &
  echo $! >"/tmp/fanout_${c}_scale.pid"

  # Cam: run until killed (not finite -t) so RTSP wait does not race encode end
  ssh "${KEY[@]}" "admin@$ip" "cat > /tmp/fanout_pub.sh && chmod +x /tmp/fanout_pub.sh" <<EOS
#!/bin/bash
pkill -INT rpicam-vid 2>/dev/null || true
pkill -x nc 2>/dev/null || true
sleep 0.2
rm -f /tmp/fanout.pts
exec stdbuf -o0 rpicam-vid -n -t 0 --mode 1920:1080:10:P \
  --width 1920 --height 1080 --framerate 30 --codec h264 --inline \
  --intra 30 --flush --bitrate 4000000 --denoise cdn_off --buffer-count 6 \
  --save-pts /tmp/fanout.pts -o - \
| /usr/bin/nc -N 192.168.7.1 ${tcp}
EOS
  ssh "${KEY[@]}" "admin@$ip" 'nohup /tmp/fanout_pub.sh >/tmp/fanout_pub.log 2>&1 &' || true
  log "start $c tcp=:$tcp raw=:$raw mtx=:$mtx"
  sleep 0.4
done

log "active: ${ACTIVE[*]:-none}"
[[ ${#ACTIVE[@]} -ge 1 ]] || exit 1
START_TS=$(date +%s)
sleep 3
log "nvr ffmpeg after start: $(pgrep -c ffmpeg || echo 0)"

rtsp_probe_file() {
  # ffprobe can hang forever on a half-dead MediaMTX path — always bound it.
  local entries=$1 cam=$2 outf=$3
  timeout 5 ffprobe -rtsp_transport tcp -v error -select_streams v:0 \
    -show_entries stream="$entries" -of csv=p=0 \
    "rtsp://127.0.0.1:8554/${cam}" >"$outf" 2>/dev/null || true
}

ready_wait=0
for _ in $(seq 1 10); do
  ok=0
  PIDS=()
  for c in "${ACTIVE[@]}"; do
    rm -f "/tmp/fanout_${c}_ready.txt"
    rtsp_probe_file "width,height,r_frame_rate" "$c" "/tmp/fanout_${c}_ready.txt" &
    PIDS+=($!)
  done
  for pid in "${PIDS[@]}"; do wait "$pid" || true; done
  for c in "${ACTIVE[@]}"; do
    out=$(cat "/tmp/fanout_${c}_ready.txt" 2>/dev/null || true)
    if [[ -n "$out" && "$out" != *",0,0,"* && "$out" != 0,0,* ]]; then
      if [[ "$out" =~ ([1-9][0-9]*),[1-9] ]]; then
        ok=$((ok + 1))
      fi
    fi
  done
  log "RTSP ready_count=$ok / ${#ACTIVE[@]} (t+${ready_wait}s) ffmpeg=$(pgrep -c ffmpeg || echo 0) load=$(cut -d' ' -f1 /proc/loadavg)"
  [[ "$ok" -eq ${#ACTIVE[@]} ]] && break
  sleep 2
  ready_wait=$((ready_wait + 2))
done

log "=== RTSP readiness ==="
PIDS=()
for c in "${ACTIVE[@]}"; do
  rm -f "/tmp/fanout_${c}_ready2.txt"
  rtsp_probe_file "codec_name,width,height,r_frame_rate" "$c" "/tmp/fanout_${c}_ready2.txt" &
  PIDS+=($!)
done
for pid in "${PIDS[@]}"; do wait "$pid" || true; done
for c in "${ACTIVE[@]}"; do
  out=$(cat "/tmp/fanout_${c}_ready2.txt" 2>/dev/null || true)
  ready=0
  if [[ -n "$out" && "$out" == h264,* ]]; then ready=1; fi
  if [[ -n "$out" && "$out" =~ ([1-9][0-9]*),[1-9] ]]; then ready=1; fi
  if [[ "$ready" -eq 1 ]]; then
    log "RTSP $c ready $out"
  else
    log "RTSP $c FAIL"
    tail -12 "/tmp/fanout_${c}_scale.log" 2>/dev/null | tee -a "$SUMMARY" || true
    tail -6 "/tmp/fanout_${c}_ingest.log" 2>/dev/null | tee -a "$SUMMARY" || true
  fi
done

log "=== live wall_fps ${DUR}s parallel (PASS >= ${PASS_LIVE}) ==="
LIVE_PIDS=()
for c in "${ACTIVE[@]}"; do
  rm -f "/tmp/fanout_${c}_liveprobe.log"
  timeout "$DUR" ffmpeg -hide_banner -loglevel info -rtsp_transport tcp \
    -i "rtsp://127.0.0.1:8554/${c}" -c copy -f null - \
    2>"/tmp/fanout_${c}_liveprobe.log" &
  LIVE_PIDS+=($!)
done
for pid in "${LIVE_PIDS[@]}"; do
  wait "$pid" || true
done
for c in "${ACTIVE[@]}"; do
  PASS_LIVE="$PASS_LIVE" python3 - "$c" "$DUR" <<'PY' | tee -a "$SUMMARY"
import os, re, sys
from pathlib import Path
cam, dur = sys.argv[1], float(sys.argv[2])
need = float(os.environ["PASS_LIVE"])
t = Path(f"/tmp/fanout_{cam}_liveprobe.log").read_text(errors="replace")
fr = re.findall(r"frame=\s*(\d+)", t)
if fr:
    w = int(fr[-1]) / dur
    print(f"live {cam} wall_fps={w:.2f} {'PASS' if w >= need else 'BELOW'}")
else:
    print(f"live {cam} FAIL")
PY
done

# Let encode run a bit more so pts span is meaningful, then stop
sleep 5

log "=== science pts (PASS >= ${PASS_SCI}) ==="
for c in "${ACTIVE[@]}"; do
  ip=${CAM_IP[$c]}
  ssh "${KEY[@]}" "admin@$ip" 'pkill -INT rpicam-vid 2>/dev/null || true; sleep 0.3; cat /tmp/fanout.pts' \
    >"/tmp/fanout_${c}.pts" 2>/dev/null || true
  ssh "${KEY[@]}" "admin@$ip" 'pkill -x nc 2>/dev/null || true' || true
  [[ -f "/tmp/fanout_${c}_ingest.pid" ]] && kill "$(cat "/tmp/fanout_${c}_ingest.pid")" 2>/dev/null || true
  [[ -f "/tmp/fanout_${c}_scale.pid" ]] && kill "$(cat "/tmp/fanout_${c}_scale.pid")" 2>/dev/null || true
done
cleanup_nvr
sleep 1

for c in "${ACTIVE[@]}"; do
  PASS_SCI="$PASS_SCI" python3 - "$c" <<'PY' | tee -a "$SUMMARY"
import os, sys
from pathlib import Path
cam = sys.argv[1]
need = float(os.environ["PASS_SCI"])
vals = []
p = Path(f"/tmp/fanout_{cam}.pts")
for ln in p.read_text().splitlines() if p.exists() else []:
    ln = ln.strip()
    if not ln or ln.startswith("#"):
        continue
    parts = ln.replace(",", " ").split()
    try:
        vals.append(float(parts[1] if len(parts) >= 2 else parts[0]))
    except Exception:
        pass
n = len(vals)
fps = (n - 1) / ((vals[-1] - vals[0]) / 1000.0) if n >= 2 else None
b = Path(f"/tmp/fanout_{cam}_science.h264").stat().st_size if Path(f"/tmp/fanout_{cam}_science.h264").exists() else 0
ok = (fps or 0) >= need
print(f"science {cam} bytes={b} pts_n={n} pts_fps={fps} {'PASS' if ok else 'FAIL'}")
print(f"RESULT_SCIENCE {cam}", "PASS" if ok else "FAIL")
PY
done
log "DONE $SUMMARY"
echo "$SUMMARY"
