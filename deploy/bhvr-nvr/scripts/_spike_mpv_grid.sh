#!/bin/bash
# Spike: 2×2 native tiles via MediaMTX RTSP (mpv), not Chromium WHEP.
# Run ON NVR. Ensures whep/start for cams, then places four mpv windows.
# Stop: _spike_mpv_grid_stop.sh
set -euo pipefail

API="${API:-http://127.0.0.1:8080}"
CAMS=(${CAMS:-bhvr-cam0 bhvr-cam1 bhvr-cam2 bhvr-cam3})
RTSP_BASE="${RTSP_BASE:-rtsp://127.0.0.1:8554}"
PIDDIR="${PIDDIR:-/tmp/bhvr-mpv-grid}"
LOGDIR="${LOGDIR:-/tmp/bhvr-mpv-grid-logs}"
mkdir -p "$PIDDIR" "$LOGDIR"

# Attach to the graphical seat (labwc / Wayland on Pi kiosk).
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
  for c in wayland-0 wayland-1; do
    if [[ -S "$XDG_RUNTIME_DIR/$c" ]]; then
      export WAYLAND_DISPLAY=$c
      break
    fi
  done
fi
# Xwayland fallback for geometry if needed
export DISPLAY="${DISPLAY:-:0}"

echo "=== native mpv 2x2 spike ==="
echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-none} DISPLAY=$DISPLAY"

# Screen size (prefer wlr-randr current mode).
read -r SW SH < <(python3 - <<'PY'
import re, subprocess
try:
    out = subprocess.check_output(["wlr-randr"], text=True, stderr=subprocess.DEVNULL)
except Exception:
    print("1024 600")
    raise SystemExit
# current mode line like: "    1024x600 px, 60.004002 Hz (preferred, current)"
m = re.search(r"(\d+)x(\d+)\s+px,.*\(.*current", out)
if m:
    print(m.group(1), m.group(2))
else:
    print("1024 600")
PY
)
TW=$((SW / 2))
TH=$((SH / 2))
echo "screen=${SW}x${SH} tile=${TW}x${TH}"

# Ensure publishers (same UDP→MediaMTX path as WHEP tiles).
curl -sS -m 10 -X POST "$API/api/preview/stop" >/dev/null || true
sleep 1
for c in "${CAMS[@]}"; do
  echo "whep/start $c"
  curl -sS -m 90 -X POST "$API/api/preview/${c}/whep/start" || true
  echo
done
sleep 4

# Wait for at least one RTSP path.
ready_n=0
for c in "${CAMS[@]}"; do
  if ffprobe -rtsp_transport tcp -v error -select_streams v:0 \
      -show_entries stream=codec_name -of csv=p=0 \
      "${RTSP_BASE}/${c}" >/dev/null 2>&1; then
    echo "RTSP ready $c"
    ready_n=$((ready_n + 1))
  else
    echo "RTSP NOT ready $c (tile will buffer/fail)"
  fi
done
echo "ready_count=$ready_n"
if [[ "$ready_n" -lt 1 ]]; then
  echo "FAIL: no RTSP paths ready" >&2
  exit 1
fi

# Kill prior spike windows.
pkill -f "mpv.*bhvr-mpv-grid" 2>/dev/null || true
sleep 0.5

# Geometry map: 0=TL 1=TR 2=BL 3=BR
geoms=(
  "${TW}x${TH}+0+0"
  "${TW}x${TH}+${TW}+0"
  "${TW}x${TH}+0+${TH}"
  "${TW}x${TH}+${TW}+${TH}"
)

i=0
for c in "${CAMS[@]}"; do
  g=${geoms[$i]}
  log="$LOGDIR/${c}.log"
  # low-latency-ish; hwdec=auto (often soft on this Pi image — still beats Chromium×4 for spike)
  nohup mpv \
    --title="bhvr-mpv-grid-$c" \
    --geometry="$g" \
    --no-audio \
    --hwdec=auto \
    --vo=gpu \
    --profile=low-latency \
    --cache=no \
    --demuxer-readahead-secs=0 \
    --framedrop=vo \
    --osd-level=1 \
    --osd-msg1="$c" \
    --rtsp-transport=tcp \
    "${RTSP_BASE}/${c}" \
    >"$log" 2>&1 &
  echo $! >"$PIDDIR/${c}.pid"
  echo "started $c pid=$(cat "$PIDDIR/${c}.pid") geom=$g"
  i=$((i + 1))
done

echo
echo "Tiles should appear on the touchscreen (above/beside Chromium)."
echo "Stop: bash ~/deploy/bhvr-nvr/scripts/_spike_mpv_grid_stop.sh"
echo "Logs: $LOGDIR"
echo "Compare feel vs Chromium WHEP at same soft 1080p30 + buffer_count=6."
echo "=== done ==="
