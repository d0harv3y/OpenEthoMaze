#!/bin/bash
# run ON nvr
set -euxo pipefail
pkill -f 'preview.*15550' 2>/dev/null || true
fuser -k 15550/udp 2>/dev/null || true
sleep 1
python3 - <<'PY'
import socket, time
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind(("0.0.0.0", 15550))
except OSError as e:
    print(f"bind_failed={e}")
    raise
sock.settimeout(1.0)
n = 0
total = 0
t0 = time.time()
src = None
first = None
while time.time() - t0 < 8:
    try:
        data, addr = sock.recvfrom(65535)
        n += 1
        total += len(data)
        src = addr
        if first is None:
            first = data[:4]
    except socket.timeout:
        pass
print(f"udp_packets={n} bytes={total} src={src} first4={first!r}")
PY
