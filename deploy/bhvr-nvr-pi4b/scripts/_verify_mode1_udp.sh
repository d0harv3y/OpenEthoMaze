#!/bin/bash
# NVR: push live_udp_mpegts.sh → cam1, start official script, listen.
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20)
CAM=admin@192.168.7.27

# Prefer freshly scp'd laptop script.
SRC=""
for p in /tmp/_live_udp_mpegts_from_laptop.sh \
         "$HOME/bhvr-cam/scripts/live_udp_mpegts.sh" \
         /tmp/live_udp_mpegts.sh; do
  if [[ -f "$p" ]]; then SRC="$p"; break; fi
done
[[ -n "$SRC" ]] || { echo "missing live_udp_mpegts.sh on NVR" >&2; exit 1; }
echo "using_src=$SRC"

sed 's/\r$//' "$SRC" > /tmp/live_udp_mpegts.lf.sh
scp "${KEY[@]}" /tmp/live_udp_mpegts.lf.sh "$CAM:/tmp/live_udp_mpegts.sh"
ssh "${KEY[@]}" "$CAM" 'mkdir -p ~/bhvr-cam/scripts
sed "s/\r$//" /tmp/live_udp_mpegts.sh > ~/bhvr-cam/scripts/live_udp_mpegts.sh
chmod +x ~/bhvr-cam/scripts/live_udp_mpegts.sh
ls -la ~/bin/ffmpeg ~/bhvr-cam/scripts/live_udp_mpegts.sh
grep -n probesize ~/bhvr-cam/scripts/live_udp_mpegts.sh || true'

# Stop encoders without matching this remote shell (avoid pkill -f bin/ffmpeg).
ssh "${KEY[@]}" "$CAM" 'killall -9 rpicam-vid 2>/dev/null || true
killall -9 ffmpeg 2>/dev/null || true
sleep 1
nohup ~/bhvr-cam/scripts/live_udp_mpegts.sh 192.168.7.1 15550 1280 720 30 2500 2 >/tmp/live_udp.log 2>&1 &
echo pid=$!
sleep 6
pgrep -a rpicam-vid || { echo DIE_rpicam; cat /tmp/live_udp.log; exit 1; }
pgrep -a ffmpeg || { echo DIE_ffmpeg; cat /tmp/live_udp.log; exit 1; }
tail -30 /tmp/live_udp.log || true'

bash /tmp/_nvr_listen_udp.sh

echo "=== kiosk ==="
systemctl is-active bhvr-kiosk-web 2>/dev/null || true
pgrep -af 'uvicorn.*app.main|bhvr-kiosk' || true
curl -sS -m 3 http://127.0.0.1:8080/api/roster 2>/dev/null | head -c 1000 || echo roster_curl_failed
python3 - <<'PY' || true
from pathlib import Path
try:
    import yaml
except ImportError:
    print("no_yaml")
    raise SystemExit(0)
for p in [Path.home()/"bhvr-kiosk"/"config.yaml", Path("/etc/bhvr-kiosk/config.yaml")]:
    if p.is_file():
        print("config", p)
        print((yaml.safe_load(p.read_text()) or {}).get("preview"))
        break
PY

ssh "${KEY[@]}" "$CAM" 'killall -9 rpicam-vid 2>/dev/null || true; killall -9 ffmpeg 2>/dev/null || true; echo cam_stopped; tail -15 /tmp/live_udp.log || true'
echo VERIFY_OK
