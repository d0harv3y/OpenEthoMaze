#!/bin/bash
# Litmus: annex-B over TCP (no SSH media) → NVR remux → MediaMTX → measure fps.
set -euo pipefail

API="${API:-http://127.0.0.1:8080}"
CAM_ID="${CAM_ID:-bhvr-cam0}"
UDP_PORT="${UDP_PORT:-15550}"
TCP_PORT="${TCP_PORT:-16550}"
DUR="${DURATION_S:-12}"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
W=1920
H=1080
FPS=30
BR=4000000

echo "=== TCP annex-B litmus ($CAM_ID) ==="

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
echo "cam_ip=$CAM_IP"

curl -sS -m 10 -X POST "$API/api/preview/stop" >/dev/null || true
sleep 1
pkill -f "ffmpeg.*127.0.0.1:${UDP_PORT}" 2>/dev/null || true
pkill -f "nc -l -p ${TCP_PORT}" 2>/dev/null || true
ssh "${KEY[@]}" "admin@${CAM_IP}" 'pkill -INT rpicam-vid 2>/dev/null || true; pkill -x nc 2>/dev/null || true' || true
sleep 1

REMUX_LOG=/tmp/litmus_tcp_annexb_remux.log
CAM_LOG=/tmp/litmus_tcp_annexb_cam.log
: >"$REMUX_LOG"
: >"$CAM_LOG"

# NVR: listen TCP → remux MPEG-TS → MediaMTX
nc -l -p "$TCP_PORT" | ffmpeg -hide_banner -loglevel warning -nostats \
  -fflags +genpts+nobuffer+flush_packets -flags low_delay \
  -probesize 1000000 -analyzeduration 500000 \
  -f h264 -i pipe:0 -c copy -muxdelay 0 -muxpreload 0 -flush_packets 1 \
  -f mpegts "udp://127.0.0.1:${UDP_PORT}?pkt_size=1316&overrun_nonfatal=1" \
  >"$REMUX_LOG" 2>&1 &
NVR_BRIDGE_PID=$!
echo "nvr_bridge_pid=$NVR_BRIDGE_PID"
sleep 0.5

# Cam: SSH launches only; media is TCP annex-B to NVR
# Write remote script to avoid quoting hell
ssh "${KEY[@]}" "admin@${CAM_IP}" "cat > /tmp/bhvr_tcp_annexb.sh && chmod +x /tmp/bhvr_tcp_annexb.sh" <<EOS
#!/bin/bash
pkill -INT rpicam-vid 2>/dev/null || true
pkill -x nc 2>/dev/null || true
sleep 0.2
exec stdbuf -o0 rpicam-vid -n -t 0 --mode 1920:1080:10:P \
  --width ${W} --height ${H} --framerate ${FPS} --codec h264 --inline \
  --intra ${FPS} --flush --bitrate ${BR} --denoise cdn_off --buffer-count 2 -o - \
| /usr/bin/nc -N 192.168.7.1 ${TCP_PORT}
EOS

ssh "${KEY[@]}" "admin@${CAM_IP}" 'nohup /tmp/bhvr_tcp_annexb.sh >/tmp/bhvr_tcp_annexb.log 2>&1 &'
sleep 5

echo "=== cam procs ==="
ssh "${KEY[@]}" "admin@${CAM_IP}" 'echo rpicam=$(pgrep -c rpicam-vid || echo 0); echo nc=$(pgrep -c nc || echo 0); tail -5 /tmp/bhvr_tcp_annexb.log || true'
echo "=== remux log ==="
tail -5 "$REMUX_LOG" || true

echo "=== wait RTSP ==="
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
  ssh "${KEY[@]}" "admin@${CAM_IP}" 'pkill -INT rpicam-vid; pkill -x nc' || true
  kill "$NVR_BRIDGE_PID" 2>/dev/null || true
  exit 1
fi

echo "=== COPY probe ${DUR}s ==="
COPY_LOG=/tmp/litmus_tcp_annexb_copy.log
timeout "$DUR" ffmpeg -hide_banner -loglevel info \
  -rtsp_transport tcp -i "rtsp://127.0.0.1:8554/${CAM_ID}" \
  -c copy -f null - 2>"$COPY_LOG" || true
python3 - "$COPY_LOG" "$DUR" <<'PY'
import re, sys
from pathlib import Path
t = Path(sys.argv[1]).read_text(errors="replace")
dur = float(sys.argv[2])
fps = re.findall(r"fps=\s*([0-9.]+)", t)
fr = re.findall(r"frame=\s*(\d+)", t)
sp = re.findall(r"speed=\s*([0-9.]+)x", t)
print("COPY fps_tail", fps[-8:] if fps else None)
print("COPY frames_tail", fr[-5:] if fr else None)
print("COPY speed_tail", sp[-5:] if sp else None)
if fr:
    last = int(fr[-1])
    wall = round(last / dur, 2)
    print("COPY last_frame", last, "wall_fps", wall)
    print("RESULT", "PASS_near_30" if wall >= 25 else "BELOW_30")
else:
    print("RESULT FAIL_no_frames")
    print(t[-800:])
PY

# Cleanup
ssh "${KEY[@]}" "admin@${CAM_IP}" 'pkill -INT rpicam-vid 2>/dev/null || true; pkill -x nc 2>/dev/null || true' || true
kill "$NVR_BRIDGE_PID" 2>/dev/null || true
pkill -f "ffmpeg.*127.0.0.1:${UDP_PORT}" 2>/dev/null || true
pkill -f "nc -l -p ${TCP_PORT}" 2>/dev/null || true
echo "=== done ==="
