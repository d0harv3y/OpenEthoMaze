#!/bin/bash
# Run on NVR: soft_fps=10, push UDP script to cam, smoke UDP, optionally flip transport.
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
NVR=10.248.238.22
PORT=15550
SRC=/tmp/bhvr-kiosk-deploy

cp "$SRC/main.py" /home/admin/bhvr-kiosk/app/main.py

python3 - <<'PY'
from pathlib import Path
import yaml
p = Path("/home/admin/bhvr-kiosk/config.yaml")
cfg = yaml.safe_load(p.read_text()) or {}
rec = cfg.setdefault("record", {})
rec["soft_fps"] = 10
rec.setdefault("bitrate_kbps", 1200)
cfg["record"] = rec
prev = cfg.setdefault("preview", {})
prev["fps_idle"] = 10
prev.setdefault("bitrate_kbps", 800)
prev.setdefault("udp_port", 15550)
prev.setdefault("nvr_host", "10.248.238.22")
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
print("record", cfg["record"])
print("preview transport", prev.get("transport"), "fps_idle", prev.get("fps_idle"))
PY

scp -i "$KEY" -o BatchMode=yes "$SRC/live_udp_mpegts.sh" "admin@${CAM}:~/bhvr-cam/scripts/live_udp_mpegts.sh"
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'sed -i "s/\r$//" ~/bhvr-cam/scripts/live_udp_mpegts.sh; chmod +x ~/bhvr-cam/scripts/live_udp_mpegts.sh; command -v ffmpeg; command -v rpicam-vid'

pkill -f 'uvicorn app.main' 2>/dev/null || true
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'pkill -INT rpicam-vid; pkill -f live_udp; pkill -f "ffmpeg.*udp"; true' || true
sleep 1

ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" bash -s <<REMOTE
set +e
nohup /home/admin/bhvr-cam/scripts/live_udp_mpegts.sh $NVR $PORT 640 480 10 800 2 >/tmp/live_udp.log 2>&1 &
sleep 3
pgrep -af 'rpicam|ffmpeg|live_udp' || echo NO_PROCESS
REMOTE

echo "=== recv 12s ==="
python3 - <<'PY'
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 15550))
s.settimeout(1.0)
n = bytes_ = 0
deadline = time.time() + 12
while time.time() < deadline:
    try:
        data, addr = s.recvfrom(65535)
        n += 1
        bytes_ += len(data)
        if n <= 5:
            print(f"pkt {n} from {addr} len={len(data)}", flush=True)
        if n >= 40:
            break
    except socket.timeout:
        print("…waiting", flush=True)
print(f"total_pkts={n} bytes={bytes_}", flush=True)
s.close()
PY

echo "=== cam log ==="
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" 'tail -40 /tmp/live_udp.log; echo ---; pgrep -af rpicam||true'

ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'pkill -INT rpicam-vid; pkill -f live_udp; pkill -f "ffmpeg.*udp"; true' || true

cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2
curl -s --max-time 3 http://127.0.0.1:8080/api/health
echo
