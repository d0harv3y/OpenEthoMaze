#!/bin/bash
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
ssh -i "$KEY" -o BatchMode=yes "admin@$CAM" 'bash -x ~/bhvr-cam/scripts/live_udp_mpegts.sh 10.248.238.22 15550 640 480 15 800 2' > /tmp/cam_udp_trace.txt 2>&1 &
PID=$!
sleep 4
kill $PID 2>/dev/null || true
wait $PID 2>/dev/null || true
echo "=== trace (head) ==="
head -80 /tmp/cam_udp_trace.txt
echo "=== cam state ==="
ssh -i "$KEY" -o BatchMode=yes "admin@$CAM" 'pgrep -af rpicam||true; pgrep -af ffmpeg||true; ls -la ~/bhvr-cam/scripts/; file ~/bhvr-cam/scripts/live_udp_mpegts.sh; head -5 ~/bhvr-cam/scripts/live_udp_mpegts.sh | od -c | head -5'
