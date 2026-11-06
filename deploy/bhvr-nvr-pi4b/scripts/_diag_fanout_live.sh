#!/bin/bash
# Quick one-cam live-path debug: is UDP raw arriving? does scale work?
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=6 -o StrictHostKeyChecking=accept-new)
IP=192.168.7.41
TCP=16570
RAW=15670
MTX=15550

pkill -f "nc -l -p ${TCP}" 2>/dev/null || true
pkill -f "udp://0.0.0.0:${RAW}" 2>/dev/null || true
ssh "${KEY[@]}" "admin@$IP" 'pkill -INT rpicam-vid 2>/dev/null || true; pkill -x nc 2>/dev/null || true; pkill -f "ffmpeg.*mpegts" 2>/dev/null || true' || true
sleep 1

echo "=== listen TCP science + UDP raw count ==="
nc -l -p "$TCP" > /tmp/diag_sci.h264 &
NC_PID=$!
timeout 8 tcpdump -ni any -c 20 udp port "$RAW" 2>/tmp/diag_tcpdump.txt &
TCPD=$!

ssh "${KEY[@]}" "admin@$IP" "cat > /tmp/diag_pub.sh && chmod +x /tmp/diag_pub.sh" <<EOS
#!/bin/bash
FF=\$HOME/bin/ffmpeg
stdbuf -o0 rpicam-vid -n -t 10000 --mode 1920:1080:10:P --width 1920 --height 1080 \
  --framerate 30 --codec h264 --inline --intra 30 --flush --bitrate 4000000 \
  --denoise cdn_off --buffer-count 6 -o - \
| tee >(nc -N 192.168.7.1 ${TCP}) \
| \$FF -hide_banner -loglevel info -f h264 -i pipe:0 -c copy \
  -f mpegts udp://192.168.7.1:${RAW}?pkt_size=1316\&overrun_nonfatal=1
EOS
ssh "${KEY[@]}" "admin@$IP" 'bash /tmp/diag_pub.sh' >/tmp/diag_cam.log 2>&1 &
CAM=$!
sleep 6
kill "$NC_PID" 2>/dev/null || true
wait "$TCPD" 2>/dev/null || true
echo "--- tcpdump ---"
cat /tmp/diag_tcpdump.txt || true
echo "--- sci bytes ---"
wc -c /tmp/diag_sci.h264 || true
echo "--- cam log tail ---"
tail -20 /tmp/diag_cam.log || true

echo "=== try scale 5s ==="
timeout 5 ffmpeg -hide_banner -loglevel info \
  -f mpegts -i "udp://0.0.0.0:${RAW}?fifo_size=1000000&overrun_nonfatal=1" \
  -vf scale=640:360,fps=15 -c:v libx264 -preset ultrafast -an \
  -f mpegts "udp://127.0.0.1:${MTX}?pkt_size=1316" 2>&1 | tail -30 || true

ssh "${KEY[@]}" "admin@$IP" 'pkill -INT rpicam-vid; pkill -x nc; pkill -f ffmpeg' || true
ffprobe -rtsp_transport tcp -v error -show_entries stream=width,height -of csv=p=0 \
  rtsp://127.0.0.1:8554/bhvr-cam0 2>&1 | head -5 || true
echo done
