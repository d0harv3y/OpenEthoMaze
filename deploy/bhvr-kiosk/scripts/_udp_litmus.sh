#!/bin/bash
# Litmus: can cam UDP-unicast reach NVR?
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
NVR=10.248.238.22
PORT=15551

pkill -f 'uvicorn app.main' 2>/dev/null || true
ssh -i "$KEY" -o BatchMode=yes "admin@$CAM" 'pkill -INT rpicam-vid; pkill -f live_udp; true' || true
sleep 1

python3 - <<'PY' &
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 15551))
s.settimeout(1.0)
deadline = time.time() + 8
got = 0
while time.time() < deadline:
    try:
        data, addr = s.recvfrom(4096)
        got += 1
        print(f"GOT from {addr}: {data[:40]!r}", flush=True)
        if got >= 3:
            break
    except socket.timeout:
        print("waiting", flush=True)
print(f"total={got}", flush=True)
s.close()
PY
RPID=$!
sleep 0.5

echo "=== cam sends 5 UDP datagrams ==="
ssh -i "$KEY" -o BatchMode=yes "admin@$CAM" python3 - <<REMOTE
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for i in range(5):
    s.sendto(f"ping-{i}".encode(), ("10.248.238.22", 15551))
    time.sleep(0.2)
print("sent", flush=True)
s.close()
REMOTE

wait $RPID

echo "=== reverse: NVR -> cam UDP ==="
ssh -i "$KEY" -o BatchMode=yes "admin@$CAM" python3 - <<'REMOTE' &
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 15552))
s.settimeout(1.0)
deadline = time.time() + 6
got = 0
while time.time() < deadline:
    try:
        data, addr = s.recvfrom(4096)
        got += 1
        print(f"CAM GOT from {addr}: {data[:40]!r}", flush=True)
        if got >= 2: break
    except socket.timeout:
        print("cam waiting", flush=True)
print(f"cam_total={got}", flush=True)
s.close()
REMOTE
CPID=$!
sleep 0.5
python3 - <<'PY'
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for i in range(5):
    s.sendto(f"pong-{i}".encode(), ("10.248.235.74", 15552))
    time.sleep(0.2)
print("nvr sent", flush=True)
s.close()
PY
wait $CPID
echo done
