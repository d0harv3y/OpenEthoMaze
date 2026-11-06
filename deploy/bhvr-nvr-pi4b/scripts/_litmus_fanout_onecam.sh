#!/bin/bash
# Litmus: one encode on cam → NVR fan-out
#   (a) science annex-B file + cam pts ≈ soft 30
#   (b) NVR scale/fps → MediaMTX → RTSP wall_fps (low-res live)
# Design: no dual encode on Zero W.
set -euo pipefail

API="${API:-http://127.0.0.1:8080}"
CAM_ID="${CAM_ID:-bhvr-cam0}"
UDP_PORT="${UDP_PORT:-15550}"
TCP_PORT="${TCP_PORT:-16560}"
DUR="${DURATION_S:-12}"
LIVE_W="${LIVE_W:-640}"
LIVE_H="${LIVE_H:-360}"
LIVE_FPS="${LIVE_FPS:-15}"
SCI_W=1920
SCI_H=1080
SCI_FPS=30
BR=4000000
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
OUT_H264="/tmp/fanout_${CAM_ID}_science.h264"
OUT_PTS_LOCAL="/tmp/fanout_${CAM_ID}.pts"
REMUX_LOG="/tmp/fanout_${CAM_ID}_nvr.log"

CAM_IP=$(python3 - <<PY
import json, urllib.request
h = json.load(urllib.request.urlopen("$API/api/cams", timeout=8))
for c in h.get("cameras") or []:
    if c.get("id") == "$CAM_ID":
        print(c["ip"]); break
else:
    raise SystemExit("cam not in roster")
PY
)
echo "=== fan-out one-cam litmus $CAM_ID @ $CAM_IP ==="
echo "science ${SCI_W}x${SCI_H}@${SCI_FPS} → file; live ${LIVE_W}x${LIVE_H}@${LIVE_FPS} → :${UDP_PORT}"

curl -sS -m 10 -X POST "$API/api/preview/stop" >/dev/null || true
sleep 1
pkill -f "nc -l -p ${TCP_PORT}" 2>/dev/null || true
pkill -f "ffmpeg.*fanout_${CAM_ID}" 2>/dev/null || true
pkill -f "ffmpeg.*127.0.0.1:${UDP_PORT}" 2>/dev/null || true
ssh "${KEY[@]}" "admin@${CAM_IP}" 'pkill -INT rpicam-vid 2>/dev/null || true; pkill -x nc 2>/dev/null || true' || true
sleep 1
rm -f "$OUT_H264" "$OUT_PTS_LOCAL" "$REMUX_LOG"

# NVR: TCP annex-B in → (1) copy science file (2) scale live → MediaMTX UDP
# shellcheck disable=SC2094
nc -l -p "$TCP_PORT" | ffmpeg -hide_banner -loglevel warning -nostats \
  -fflags +genpts+nobuffer+flush_packets -flags low_delay \
  -probesize 1000000 -analyzeduration 500000 \
  -f h264 -i pipe:0 \
  -map 0:v -c:v copy -f h264 "$OUT_H264" \
  -map 0:v -vf "scale=${LIVE_W}:${LIVE_H},fps=${LIVE_FPS}" \
  -c:v libx264 -preset ultrafast -tune zerolatency -g "$LIVE_FPS" \
  -an -f mpegts "udp://127.0.0.1:${UDP_PORT}?pkt_size=1316&overrun_nonfatal=1" \
  >"$REMUX_LOG" 2>&1 &
NVR_PID=$!
echo "nvr_fanout_pid=$NVR_PID"
sleep 0.5

# Cam: one encode + pts; media over TCP (SSH only launches)
ssh "${KEY[@]}" "admin@${CAM_IP}" "cat > /tmp/fanout_pub.sh && chmod +x /tmp/fanout_pub.sh" <<EOS
#!/bin/bash
pkill -INT rpicam-vid 2>/dev/null || true
pkill -x nc 2>/dev/null || true
sleep 0.2
rm -f /tmp/fanout.pts
exec stdbuf -o0 rpicam-vid -n -t 0 --mode 1920:1080:10:P \
  --width ${SCI_W} --height ${SCI_H} --framerate ${SCI_FPS} --codec h264 --inline \
  --intra ${SCI_FPS} --flush --bitrate ${BR} --denoise cdn_off --buffer-count 6 \
  --save-pts /tmp/fanout.pts -o - \
| /usr/bin/nc -N 192.168.7.1 ${TCP_PORT}
EOS
ssh "${KEY[@]}" "admin@${CAM_IP}" 'nohup /tmp/fanout_pub.sh >/tmp/fanout_pub.log 2>&1 &'
sleep 5

echo "=== wait RTSP ${CAM_ID} ==="
ready=0
for i in $(seq 1 20); do
  if out=$(ffprobe -rtsp_transport tcp -v error -select_streams v:0 \
      -show_entries stream=codec_name,width,height,r_frame_rate -of csv=p=0 \
      "rtsp://127.0.0.1:8554/${CAM_ID}" 2>/dev/null); then
    echo "ready $out"
    ready=1
    break
  fi
  echo wait_$i
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "FAIL: RTSP never ready"
  tail -20 "$REMUX_LOG" || true
  ssh "${KEY[@]}" "admin@${CAM_IP}" 'cat /tmp/fanout_pub.log' || true
fi

echo "=== live RTSP copy ${DUR}s (scaled path) ==="
timeout "$DUR" ffmpeg -hide_banner -loglevel info -rtsp_transport tcp \
  -i "rtsp://127.0.0.1:8554/${CAM_ID}" -c copy -f null - \
  2>/tmp/fanout_live_copy.log || true
python3 - <<PY
import re
from pathlib import Path
t = Path("/tmp/fanout_live_copy.log").read_text(errors="replace")
fr = re.findall(r"frame=\s*(\d+)", t)
fps = re.findall(r"fps=\s*([0-9.]+)", t)
sp = re.findall(r"speed=\s*([0-9.]+)x", t)
dur = float("$DUR")
print("live fps_tail", fps[-6:] if fps else None)
print("live frames_tail", fr[-4:] if fr else None)
print("live speed_tail", sp[-4:] if sp else None)
if fr:
    print("live wall_fps", round(int(fr[-1]) / dur, 2))
PY
ffprobe -rtsp_transport tcp -v error -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate,codec_name -of default=nw=1 \
  "rtsp://127.0.0.1:8554/${CAM_ID}" 2>/dev/null || true

# Stop cam publish; pull pts
ssh "${KEY[@]}" "admin@${CAM_IP}" 'pkill -INT rpicam-vid 2>/dev/null || true; pkill -x nc 2>/dev/null || true; sleep 0.5; cat /tmp/fanout.pts' \
  >"$OUT_PTS_LOCAL" 2>/dev/null || true
sleep 1
kill "$NVR_PID" 2>/dev/null || true
pkill -f "nc -l -p ${TCP_PORT}" 2>/dev/null || true
pkill -f "ffmpeg.*${OUT_H264}" 2>/dev/null || true

echo "=== science pts ==="
ls -l "$OUT_H264" "$OUT_PTS_LOCAL" 2>/dev/null || true
python3 - <<PY
from pathlib import Path
pts = Path("$OUT_PTS_LOCAL")
h264 = Path("$OUT_H264")
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
print(f"science bytes={h264.stat().st_size if h264.exists() else 0} pts_n={n} pts_fps={fps}")
if fps is not None:
    print("RESULT_SCIENCE", "PASS" if fps >= 25 else "BELOW_30")
else:
    print("RESULT_SCIENCE FAIL")
PY
echo "=== remux log (tail) ==="
tail -15 "$REMUX_LOG" || true
echo "=== done one-cam ==="
