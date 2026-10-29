#!/bin/bash
set -uo pipefail
NVR_IP=10.248.238.22
PORT=15550
CAM=10.248.235.74
KEY=/home/admin/.ssh/id_ed25519_bhvr

pkill -f 'uvicorn app.main' 2>/dev/null || true
sleep 1

echo "=== start cam publish ==="
ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=10 "admin@$CAM" bash -s <<REMOTE
set +e
pkill -INT rpicam-vid 2>/dev/null
pkill -f live_udp_mpegts 2>/dev/null
sleep 0.3
nohup /home/admin/bhvr-cam/scripts/live_udp_mpegts.sh $NVR_IP $PORT 640 480 15 800 2 >/tmp/live_udp.log 2>&1 &
sleep 1
pgrep -af 'rpicam|ffmpeg|live_udp' || echo NO_PROCESS
echo ---log---
cat /tmp/live_udp.log
REMOTE

echo "=== recv 5s ==="
python3 - <<'PY'
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("0.0.0.0", 15550))
except OSError as e:
    print("bind_fail", e)
    raise
s.settimeout(1.0)
n = 0
bytes_ = 0
deadline = time.time() + 5
while time.time() < deadline:
    try:
        data, addr = s.recvfrom(65535)
        n += 1
        bytes_ += len(data)
        if n <= 5:
            print(f"pkt {n} from {addr} len={len(data)}")
    except socket.timeout:
        print("…waiting")
print(f"total_pkts={n} bytes={bytes_}")
s.close()
PY

ssh -i "$KEY" -o BatchMode=yes "admin@$CAM" "pkill -f live_udp_mpegts; pkill -INT rpicam-vid; true" || true
echo done
