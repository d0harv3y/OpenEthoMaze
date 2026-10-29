#!/bin/bash
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
NVR=10.248.238.22
PORT=15550

pkill -f 'uvicorn app.main' 2>/dev/null || true
ssh -i "$KEY" -o BatchMode=yes "admin@$CAM" 'pkill -INT rpicam-vid; pkill -f live_udp; pkill -f "ffmpeg.*udp"; true' || true
sleep 1

ssh -i "$KEY" -o BatchMode=yes "admin@$CAM" bash -s <<REMOTE
set +e
nohup /home/admin/bhvr-cam/scripts/live_udp_mpegts.sh $NVR $PORT 640 480 15 800 2 >/tmp/live_udp.log 2>&1 &
sleep 2
pgrep -af 'rpicam|ffmpeg|live_udp' || echo NO_PROCESS
REMOTE

echo "=== recv 15s ==="
python3 - <<'PY'
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 15550))
s.settimeout(1.0)
n = bytes_ = 0
deadline = time.time() + 15
while time.time() < deadline:
    try:
        data, addr = s.recvfrom(65535)
        n += 1
        bytes_ += len(data)
        if n <= 5:
            print(f"pkt {n} from {addr} len={len(data)}", flush=True)
        if n >= 30:
            break
    except socket.timeout:
        print("…waiting", flush=True)
print(f"total_pkts={n} bytes={bytes_}", flush=True)
s.close()
PY

echo "=== cam log tail ==="
ssh -i "$KEY" -o BatchMode=yes "admin@$CAM" 'tail -30 /tmp/live_udp.log; pgrep -af rpicam||true'

ssh -i "$KEY" -o BatchMode=yes "admin@$CAM" 'pkill -INT rpicam-vid; pkill -f live_udp; pkill -f "ffmpeg.*udp"; true' || true

cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2
curl -s --max-time 3 http://127.0.0.1:8080/api/health
echo
