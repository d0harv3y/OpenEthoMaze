#!/bin/bash
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20)
CAM=admin@192.168.7.27

echo "=== kiosk preview ==="
python3 -c 'import yaml; from pathlib import Path; print(yaml.safe_load(Path.home().joinpath("bhvr-kiosk/config.yaml").read_text())["preview"])'

curl -sS -X POST 'http://127.0.0.1:8080/api/preview/stop' || true
ssh "${KEY[@]}" "$CAM" 'killall -9 rpicam-vid 2>/dev/null || true; killall -9 ffmpeg 2>/dev/null || true; true'
sleep 1

scp "${KEY[@]}" /tmp/_dig_fps_on_cam.sh "$CAM:/tmp/_dig_fps_on_cam.sh"
ssh "${KEY[@]}" "$CAM" 'sed -i "s/\r$//" /tmp/_dig_fps_on_cam.sh; bash /tmp/_dig_fps_on_cam.sh'

echo "=== UDP bitrate 6s on :15551 (cam publish) ==="
ssh "${KEY[@]}" "$CAM" 'killall -9 rpicam-vid 2>/dev/null || true; killall -9 ffmpeg 2>/dev/null || true; nohup bash /tmp/_dig_fps_udp_pub.sh >/tmp/fps_udp_pub.log 2>&1 &' || true
# publish helper written below if present
if ssh "${KEY[@]}" "$CAM" 'test -x /tmp/_dig_fps_udp_pub.sh'; then
  sleep 2
  python3 - <<'PY'
import socket, time
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 15551))
sock.settimeout(0.5)
n=total=0
t0=time.time()
while time.time()-t0 < 6:
    try:
        d,_=sock.recvfrom(65535); n+=1; total+=len(d)
    except socket.timeout:
        pass
dt=time.time()-t0
print(f"udp_packets={n} bytes={total} dt={dt:.2f} pps={n/dt:.1f} mbps={8*total/dt/1e6:.2f}")
PY
  ssh "${KEY[@]}" "$CAM" 'killall -9 rpicam-vid 2>/dev/null || true; killall -9 ffmpeg 2>/dev/null || true; true'
fi

echo DIG_FPS_DONE
