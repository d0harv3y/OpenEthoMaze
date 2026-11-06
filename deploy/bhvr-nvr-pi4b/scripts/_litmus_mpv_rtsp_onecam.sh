#!/bin/bash
# Litmus: one-cam native player via MediaMTX RTSP (vs Chromium WHEP).
# Prefer mpv; fall back to ffplay if mpv missing.
# Target shell on NVR: bash.
set -euo pipefail

API="${API:-http://127.0.0.1:8080}"
CAM_ID="${CAM_ID:-bhvr-cam0}"
RTSP_URL="${RTSP_URL:-rtsp://127.0.0.1:8554/${CAM_ID}}"
MTX_YML="${MTX_YML:-$HOME/bhvr-mediamtx/mediamtx.yml}"
DURATION_S="${DURATION_S:-12}"
DISPLAY_ENV="${DISPLAY_ENV:-:0}"

echo "=== native RTSP litmus cam=${CAM_ID} duration=${DURATION_S}s ==="

if [[ ! -f "$MTX_YML" ]]; then
  echo "FAIL: mediamtx.yml not found at $MTX_YML" >&2
  find "$HOME" /etc /opt -name mediamtx.yml 2>/dev/null || true
  exit 1
fi
echo "yml=$MTX_YML"

# Enable RTSP read on MediaMTX if currently false (idempotent).
python3 - "$MTX_YML" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text()
changed = False
if "rtsp: false" in text:
    text = text.replace("rtsp: false", "rtsp: true", 1)
    changed = True
if "rtspAddress:" not in text and "rtsp: true" in text:
    text = text.replace("rtsp: true", "rtsp: true\nrtspAddress: :8554", 1)
    changed = True
if changed:
    p.write_text(text)
    print("mediamtx.yml: enabled rtsp (:8554)")
else:
    print("mediamtx.yml: rtsp already enabled (or nonstandard form)")
PY

# Restart MediaMTX only if RTSP is not already listening (avoids sudo when healthy).
if ss -tln | grep -q ':8554'; then
  echo "RTSP :8554 already up — skip restart"
else
  restarted=0
  for unit in bhvr-mediamtx mediamtx; do
    if systemctl cat "${unit}.service" >/dev/null 2>&1; then
      if sudo -n systemctl restart "$unit" 2>/dev/null; then
        echo "restarted $unit"
        restarted=1
        break
      else
        echo "WARN: need sudo to restart $unit — run: sudo systemctl restart $unit"
      fi
    fi
  done
  if [[ "$restarted" -eq 0 ]]; then
    echo "WARN: no passwordless restart — enable rtsp in yml then: sudo systemctl restart bhvr-mediamtx"
  fi
  sleep 2
fi

echo "=== listeners ==="
ss -lntp 2>/dev/null | grep -E '8554|8889' || true

# Ensure one cam is publishing into MediaMTX (kiosk WHEP start → UDP ingest).
echo "=== ensure preview $CAM_ID ==="
curl -sS -m 10 -X POST "$API/api/preview/stop" >/dev/null || true
sleep 1
curl -sS -m 90 -X POST "$API/api/preview/${CAM_ID}/whep/start"
echo
sleep 3
code=$(curl -sS -m 5 -o /dev/null -w "%{http_code}" -X OPTIONS "http://127.0.0.1:8889/${CAM_ID}/whep" || echo 000)
echo "whep OPTIONS $CAM_ID => $code"

# Wait until MediaMTX has a live track (avoid DESCRIBE 404 race after restart).
echo "=== wait RTSP path ready ==="
ready=0
for i in $(seq 1 20); do
  if ffprobe -rtsp_transport tcp -v error \
      -select_streams v:0 -show_entries stream=codec_name,width,height \
      -of csv=p=0 "$RTSP_URL" >/tmp/litmus_rtsp_probe.txt 2>/dev/null; then
    echo "ready_after=${i}s $(cat /tmp/litmus_rtsp_probe.txt)"
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "FAIL: RTSP path never ready" >&2
  exit 1
fi

PLAYER=""
if command -v mpv >/dev/null 2>&1; then
  PLAYER=mpv
elif command -v ffplay >/dev/null 2>&1; then
  PLAYER=ffplay
  echo "WARN: mpv not installed; using ffplay (same native-player class)."
  echo "      Install on NVR: sudo apt install -y mpv"
else
  echo "FAIL: neither mpv nor ffplay found" >&2
  exit 1
fi
echo "player=$PLAYER url=$RTSP_URL display=$DISPLAY_ENV"

LOG=/tmp/litmus_rtsp_${CAM_ID}.log
FPS_LOG=/tmp/litmus_rtsp_${CAM_ID}_fps.log
: >"$LOG"
: >"$FPS_LOG"

echo "=== ffmpeg RTSP decode probe (${DURATION_S}s) ==="
timeout "${DURATION_S}" ffmpeg -hide_banner -loglevel info \
  -rtsp_transport tcp -i "$RTSP_URL" \
  -an -f null - 2>"$FPS_LOG" || true
echo "--- ffmpeg stderr (tail) ---"
tail -40 "$FPS_LOG" || true

CAM_ID="$CAM_ID" DURATION_S="$DURATION_S" python3 - <<'PY'
import os, re
from pathlib import Path
cam = os.environ["CAM_ID"]
dur = float(os.environ.get("DURATION_S", "12"))
text = Path(f"/tmp/litmus_rtsp_{cam}_fps.log").read_text(errors="replace")
fps = re.findall(r"fps=\s*([0-9.]+)", text)
frames = re.findall(r"frame=\s*(\d+)", text)
speed = re.findall(r"speed=\s*([0-9.]+)x", text)
print("ffmpeg_fps_samples_tail", fps[-8:] if fps else None)
print("ffmpeg_frame_samples_tail", frames[-5:] if frames else None)
print("ffmpeg_speed_samples_tail", speed[-5:] if speed else None)
if frames:
    print("ffmpeg_last_frame", frames[-1], "wall_implied_fps", round(int(frames[-1]) / dur, 2))
bad = any(x in text for x in ("Connection refused", "404 Not Found", "Server returned 404", "Immediate exit"))
if bad and not frames:
    print("RESULT: RTSP connect FAILED")
elif frames:
    print("RESULT: RTSP read OK (see fps samples)")
else:
    print("RESULT: inconclusive — inspect", f"/tmp/litmus_rtsp_{cam}_fps.log")
PY

echo "=== on-screen peek (5s, DISPLAY=$DISPLAY_ENV) ==="
export DISPLAY="$DISPLAY_ENV"
if [[ "$PLAYER" == "mpv" ]]; then
  timeout 5 mpv --really-quiet --no-audio --vo=gpu --hwdec=auto \
    --title="bhvr-rtsp-litmus-$CAM_ID" "$RTSP_URL" >>"$LOG" 2>&1 || true
else
  timeout 5 ffplay -hide_banner -loglevel warning -an -autoexit \
    -window_title "bhvr-rtsp-litmus-$CAM_ID" \
    -rtsp_transport tcp "$RTSP_URL" >>"$LOG" 2>&1 || true
fi
echo "on-screen exit done (check touchscreen for brief window)"
echo "logs: $FPS_LOG $LOG"
echo "=== done ==="
