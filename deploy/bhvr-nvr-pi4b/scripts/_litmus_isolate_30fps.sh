#!/bin/bash
# Isolate where soft 1080p30 dies: local cam file vs TCP→file vs TCP→MediaMTX.
set -euo pipefail

API="${API:-http://127.0.0.1:8080}"
CAM_ID="${CAM_ID:-bhvr-cam0}"
TCP_PORT=16551
UDP_PORT=15550
DUR=8
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
W=1920; H=1080; FPS=30; BR=4000000

CAM_IP=$(python3 - <<PY
import json, urllib.request
h = json.load(urllib.request.urlopen("$API/api/cams", timeout=8))
for c in h.get("cameras") or []:
    if c.get("id") == "$CAM_ID":
        print(c["ip"]); break
else:
    raise SystemExit("cam missing")
PY
)
echo "cam=$CAM_IP"

curl -sS -m 10 -X POST "$API/api/preview/stop" >/dev/null || true
sleep 1
ssh "${KEY[@]}" "admin@${CAM_IP}" 'pkill -INT rpicam-vid 2>/dev/null || true; pkill -x nc 2>/dev/null || true' || true
pkill -f "nc -l -p ${TCP_PORT}" 2>/dev/null || true
pkill -f "ffmpeg.*127.0.0.1:${UDP_PORT}" 2>/dev/null || true
sleep 1

pts_fps() {
  # pts file from rpicam --save-pts: "# timecode format" then "frame pts_ms"
  python3 - "$1" <<'PY'
import sys
from pathlib import Path
lines = Path(sys.argv[1]).read_text(errors="replace").splitlines()
pts = []
for ln in lines:
    ln = ln.strip()
    if not ln or ln.startswith("#"):
        continue
    parts = ln.replace(",", " ").split()
    if len(parts) >= 2:
        try:
            pts.append(float(parts[1]))
        except ValueError:
            pass
    elif len(parts) == 1:
        try:
            pts.append(float(parts[0]))
        except ValueError:
            pass
if len(pts) < 2:
    print("pts_frames", len(pts), "fps", "n/a")
else:
    # rpicam pts often in microseconds or milliseconds — detect
    span = pts[-1] - pts[0]
    n = len(pts) - 1
    if span > 1e6:  # microseconds
        fps = n / (span / 1e6)
        unit = "us"
    elif span > 1e3:  # milliseconds
        fps = n / (span / 1e3)
        unit = "ms"
    else:
        fps = n / span
        unit = "s"
    print(f"pts_frames {len(pts)} span_{unit} {span:.1f} fps {fps:.2f}")
PY
}

echo
echo "===== A: cam local file ${DUR}s (leg-B shape, no network) ====="
ssh "${KEY[@]}" "admin@${CAM_IP}" "rm -f /tmp/isoA.h264 /tmp/isoA.pts; \
  timeout ${DUR} rpicam-vid -n -t $((DUR*1000)) --mode 1920:1080:10:P \
    --width $W --height $H --framerate $FPS --codec h264 --inline \
    --intra $FPS --flush --bitrate $BR --denoise cdn_off --buffer-count 2 \
    --save-pts /tmp/isoA.pts -o /tmp/isoA.h264; \
  ls -l /tmp/isoA.h264 /tmp/isoA.pts; \
  echo -n 'bytes '; wc -c </tmp/isoA.h264"
ssh "${KEY[@]}" "admin@${CAM_IP}" 'cat /tmp/isoA.pts' > /tmp/isoA.pts
pts_fps /tmp/isoA.pts

echo
echo "===== B: TCP annex-B → NVR file ${DUR}s (no MediaMTX) ====="
rm -f /tmp/isoB.h264
nc -l -p "$TCP_PORT" > /tmp/isoB.h264 &
NCPID=$!
sleep 0.3
ssh "${KEY[@]}" "admin@${CAM_IP}" "cat > /tmp/isoB_pub.sh && chmod +x /tmp/isoB_pub.sh" <<EOS
#!/bin/bash
pkill -INT rpicam-vid 2>/dev/null || true
sleep 0.2
exec timeout ${DUR} stdbuf -o0 rpicam-vid -n -t $((DUR*1000)) --mode 1920:1080:10:P \
  --width ${W} --height ${H} --framerate ${FPS} --codec h264 --inline \
  --intra ${FPS} --flush --bitrate ${BR} --denoise cdn_off --buffer-count 2 \
  --save-pts /tmp/isoB.pts -o - \
| /usr/bin/nc -N 192.168.7.1 ${TCP_PORT}
EOS
ssh "${KEY[@]}" "admin@${CAM_IP}" '/tmp/isoB_pub.sh' || true
wait "$NCPID" 2>/dev/null || true
sleep 0.5
ls -l /tmp/isoB.h264 || true
echo -n 'nvr_bytes '; wc -c </tmp/isoB.h264 || echo 0
# count NAL-ish frames via ffmpeg
timeout 30 ffmpeg -hide_banner -loglevel error -f h264 -i /tmp/isoB.h264 -c copy -f null - 2>/tmp/isoB_ff.log || true
python3 - <<'PY'
import re
from pathlib import Path
# re-run with info to get frame count
PY
FR=$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 -f h264 /tmp/isoB.h264 2>/dev/null || echo 0)
echo "nvr_ffprobe_frames $FR implied_fps $(python3 -c "print(round($FR/$DUR,2) if $FR else 'n/a')")"
ssh "${KEY[@]}" "admin@${CAM_IP}" 'cat /tmp/isoB.pts' > /tmp/isoB.pts 2>/dev/null || true
pts_fps /tmp/isoB.pts

echo
echo "===== C: TCP annex-B → remux → MediaMTX COPY ${DUR}s ====="
pkill -f "nc -l -p ${TCP_PORT}" 2>/dev/null || true
pkill -f "ffmpeg.*127.0.0.1:${UDP_PORT}" 2>/dev/null || true
ssh "${KEY[@]}" "admin@${CAM_IP}" 'pkill -INT rpicam-vid 2>/dev/null || true; pkill -x nc 2>/dev/null || true' || true
sleep 1

nc -l -p "$TCP_PORT" | ffmpeg -hide_banner -loglevel warning -nostats \
  -fflags +genpts+nobuffer+flush_packets -flags low_delay \
  -probesize 1000000 -analyzeduration 500000 \
  -f h264 -i pipe:0 -c copy -muxdelay 0 -muxpreload 0 -flush_packets 1 \
  -f mpegts "udp://127.0.0.1:${UDP_PORT}?pkt_size=1316&overrun_nonfatal=1" \
  >/tmp/isoC_remux.log 2>&1 &
BRPID=$!
sleep 0.4
ssh "${KEY[@]}" "admin@${CAM_IP}" "cat > /tmp/isoC_pub.sh && chmod +x /tmp/isoC_pub.sh" <<EOS
#!/bin/bash
pkill -INT rpicam-vid 2>/dev/null || true
sleep 0.2
exec stdbuf -o0 rpicam-vid -n -t 0 --mode 1920:1080:10:P \
  --width ${W} --height ${H} --framerate ${FPS} --codec h264 --inline \
  --intra ${FPS} --flush --bitrate ${BR} --denoise cdn_off --buffer-count 2 \
  --save-pts /tmp/isoC.pts -o - \
| /usr/bin/nc -N 192.168.7.1 ${TCP_PORT}
EOS
ssh "${KEY[@]}" "admin@${CAM_IP}" 'nohup /tmp/isoC_pub.sh >/tmp/isoC_pub.log 2>&1 &'
sleep 4
for i in $(seq 1 10); do
  ffprobe -rtsp_transport tcp -v error -select_streams v:0 -show_entries stream=codec_name \
    -of csv=p=0 "rtsp://127.0.0.1:8554/${CAM_ID}" >/dev/null 2>&1 && break
  sleep 1
done
timeout "$DUR" ffmpeg -hide_banner -loglevel info -rtsp_transport tcp \
  -i "rtsp://127.0.0.1:8554/${CAM_ID}" -c copy -f null - 2>/tmp/isoC_copy.log || true
python3 - <<PY
import re
from pathlib import Path
t = Path("/tmp/isoC_copy.log").read_text(errors="replace")
fr = re.findall(r"frame=\s*(\d+)", t)
sp = re.findall(r"speed=\s*([0-9.]+)x", t)
fps = re.findall(r"fps=\s*([0-9.]+)", t)
print("MTX fps_tail", fps[-6:] if fps else None)
print("MTX frames_tail", fr[-4:] if fr else None)
print("MTX speed_tail", sp[-4:] if sp else None)
if fr:
    print("MTX wall_fps", round(int(fr[-1]) / $DUR, 2))
PY
ssh "${KEY[@]}" "admin@${CAM_IP}" 'pkill -INT rpicam-vid; pkill -x nc; cat /tmp/isoC.pts' > /tmp/isoC.pts 2>/dev/null || true
pts_fps /tmp/isoC.pts
kill "$BRPID" 2>/dev/null || true
pkill -f "ffmpeg.*127.0.0.1:${UDP_PORT}" 2>/dev/null || true
pkill -f "nc -l -p ${TCP_PORT}" 2>/dev/null || true

echo
echo "===== summary ====="
echo "A=local file pts; B=TCP to NVR file; C=TCP via MediaMTX"
echo "done"
