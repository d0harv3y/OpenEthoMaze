#!/bin/bash
# Manual dual UDP publish (bypass kiosk) to verify MediaMTX + USB can carry 2 streams.
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
CAM0="${1:-192.168.7.41}"
CAM1="${2:-192.168.7.27}"

curl -sS -m 10 -X POST http://127.0.0.1:8080/api/preview/stop >/dev/null || true
sleep 1

start_one() {
  local ip=$1 port=$2 log=$3
  ssh "${KEY[@]}" "admin@$ip" \
    "pkill -INT rpicam-vid 2>/dev/null || true; sleep 0.2; nohup ~/bhvr-cam/scripts/live_udp_mpegts.sh 192.168.7.1 ${port} 1280 720 15 2500 2 auto >${log} 2>&1 & echo started"
}

echo "start cam0@$CAM0 :15550"
start_one "$CAM0" 15550 /tmp/live0.log || echo "WARN: start cam0 failed"
echo "start cam1@$CAM1 :15551"
start_one "$CAM1" 15551 /tmp/live1.log || echo "WARN: start cam1 failed"
sleep 6

echo "=== cam0 ==="
ssh "${KEY[@]}" "admin@$CAM0" 'hostname; echo rpicam=$(pgrep -c rpicam-vid || echo 0); echo ffmpeg=$(pgrep -c ffmpeg || echo 0); tail -8 /tmp/live0.log' || true
echo "=== cam1 ==="
ssh "${KEY[@]}" "admin@$CAM1" 'hostname; echo rpicam=$(pgrep -c rpicam-vid || echo 0); echo ffmpeg=$(pgrep -c ffmpeg || echo 0); tail -8 /tmp/live1.log' || true
echo "=== whep ==="
for c in bhvr-cam0 bhvr-cam1; do
  code=$(curl -sS -m 5 -o /dev/null -w "%{http_code}" -X OPTIONS "http://127.0.0.1:8889/$c/whep" || echo fail)
  echo "$c options=$code"
done
