#!/bin/bash
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15)
ssh "${KEY[@]}" admin@192.168.7.27 'bash -s' <<'EOC'
set -euo pipefail
pkill -9 rpicam-vid 2>/dev/null || true
pkill -9 -f bin/ffmpeg 2>/dev/null || true
sleep 1
echo "=== rpicam 3s to file ==="
timeout 4 rpicam-vid -n -t 3000 --width 1280 --height 720 --framerate 30 --codec h264 --inline --bitrate 2500000 -o /tmp/t.h264 2>/tmp/rpicam.err || true
ls -la /tmp/t.h264
wc -c /tmp/t.h264
echo "=== ffmpeg remux file to udp (5s) ==="
timeout 5 ~/bin/ffmpeg -hide_banner -loglevel info -re -fflags +genpts -f h264 -i /tmp/t.h264 -c copy -f mpegts "udp://192.168.7.1:15550?pkt_size=1316" 2>/tmp/ff.err || true
tail -30 /tmp/ff.err
tail -20 /tmp/rpicam.err
EOC

echo "=== listen while cam remux (parallel) ==="
# relaunch publish of file in background then listen
ssh "${KEY[@]}" admin@192.168.7.27 'pkill -9 -f bin/ffmpeg 2>/dev/null; ~/bin/ffmpeg -hide_banner -loglevel warning -re -stream_loop -1 -fflags +genpts -f h264 -i /tmp/t.h264 -c copy -f mpegts udp://192.168.7.1:15550?pkt_size=1316 >/tmp/ff2.err 2>&1' &
SP=$!
sleep 1
python3 - <<'PY'
import socket, time
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", 15550))
sock.settimeout(1.0)
n=0; total=0; t0=time.time()
while time.time()-t0 < 6:
    try:
        data,_=sock.recvfrom(65535)
        n+=1; total+=len(data)
    except socket.timeout:
        pass
print(f"udp_packets={n} bytes={total}")
PY
kill $SP 2>/dev/null || true
ssh "${KEY[@]}" admin@192.168.7.27 'pkill -9 -f "ffmpeg.*15550" 2>/dev/null; tail -10 /tmp/ff2.err || true'
