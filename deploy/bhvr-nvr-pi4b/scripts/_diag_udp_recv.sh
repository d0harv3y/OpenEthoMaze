#!/bin/bash
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=6 -o StrictHostKeyChecking=accept-new)
IP=192.168.7.41
RAW=15671
echo "=== routes/addrs ==="
ip -4 addr show br-bhvr 2>/dev/null | head -10 || true
ssh "${KEY[@]}" "admin@$IP" 'ip -4 route get 192.168.7.1; ip -4 -o addr show usb0'

echo "=== python UDP echo (NVR listen, cam send) ==="
python3 - <<'PY' &
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 15671))
s.settimeout(8)
total = 0
try:
    while True:
        data, addr = s.recvfrom(65535)
        total += len(data)
        print(f"got {len(data)} from {addr} total={total}", flush=True)
        if total > 50000:
            break
except Exception as e:
    print("recv_done", type(e).__name__, total, flush=True)
print("FINAL", total, flush=True)
PY
RX=$!
sleep 0.5
ssh "${KEY[@]}" "admin@$IP" 'python3 - <<"PY"
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for i in range(40):
    s.sendto(b"x" * 1200, ("192.168.7.1", 15671))
    time.sleep(0.05)
print("sent", flush=True)
PY'
wait "$RX" || true

echo "=== ffmpeg UDP mpegts concurrent ==="
timeout 10 ffmpeg -hide_banner -loglevel info -y \
  -f mpegts -i "udp://0.0.0.0:${RAW}?reuse=1&fifo_size=1000000&overrun_nonfatal=1" \
  -c copy -f null - >/tmp/udp_ff_rx.log 2>&1 &
FFRX=$!
sleep 1
ssh "${KEY[@]}" "admin@$IP" 'FF=$HOME/bin/ffmpeg; timeout 6 stdbuf -o0 rpicam-vid -n -t 5000 --width 640 --height 480 --framerate 15 --codec h264 --inline --bitrate 1000000 --denoise cdn_off -o - | $FF -hide_banner -loglevel warning -f h264 -i pipe:0 -c copy -f mpegts udp://192.168.7.1:15671?pkt_size=1316' >/tmp/udp_ff_tx.log 2>&1 || true
wait "$FFRX" 2>/dev/null || true
echo "--- rx ---"; tail -20 /tmp/udp_ff_rx.log
echo "--- tx ---"; tail -15 /tmp/udp_ff_tx.log
