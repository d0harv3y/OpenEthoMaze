#!/bin/bash
# Mirror app UDP preview path without HTTP.
set -uo pipefail
KEY=/home/admin/.ssh/id_ed25519_bhvr
CAM=10.248.235.74
NVR=10.248.238.22
PORT=15550

cp /tmp/bhvr-kiosk-deploy/main.py /home/admin/bhvr-kiosk/app/main.py
cp /tmp/bhvr-kiosk-deploy/preview.py /home/admin/bhvr-kiosk/app/preview.py

pkill -f 'uvicorn app.main' 2>/dev/null || true
ssh -i "$KEY" -o BatchMode=yes "admin@${CAM}" \
  'pkill -INT rpicam-vid; pkill -f live_udp; pkill -f "ffmpeg.*udp"; true' || true
sleep 1

cd /home/admin/bhvr-kiosk
python3 - <<'PY'
import select, subprocess, time
from pathlib import Path
from app.preview import (
    cam_live_udp_remote,
    nvr_ffmpeg_udp_to_mpegts_pipe,
    preview_settings,
)

cfg = {
    "ssh_user": "admin",
    "ssh_identity_file": "/home/admin/.ssh/id_ed25519_bhvr",
    "preview": {
        "transport": "udp",
        "udp_port": 15550,
        "nvr_host": "10.248.238.22",
        "width": 640,
        "height": 480,
        "fps_idle": 10,
        "bitrate_kbps": 800,
        "buffer_count": 2,
    },
}
settings = preview_settings(cfg)
host = "10.248.235.74"
nvr_ip = "10.248.238.22"
port = 15550
remote = cam_live_udp_remote(settings, nvr_ip, port)
print("remote:", remote[:120], "...")

cam_err = open("/tmp/mirror-cam.log", "wb")
cam = subprocess.Popen(
    [
        "ssh",
        "-i",
        cfg["ssh_identity_file"],
        "-o",
        "BatchMode=yes",
        "-o",
        "IdentitiesOnly=yes",
        f"admin@{host}",
        remote,
    ],
    stdout=subprocess.DEVNULL,
    stderr=cam_err,
    stdin=subprocess.DEVNULL,
)
print("cam pid", cam.pid)
time.sleep(4.0)

ff_err = open("/tmp/mirror-ff.log", "wb")
cmd = nvr_ffmpeg_udp_to_mpegts_pipe(port)
print("ff:", " ".join(cmd))
ff = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=ff_err, stdin=subprocess.DEVNULL, bufsize=0)
assert ff.stdout is not None
deadline = time.time() + 12
got = 0
out = Path("/tmp/mirror_udp.ts")
with out.open("wb") as f:
    while time.time() < deadline:
        if ff.poll() is not None:
            print("ff exited", ff.returncode)
            break
        r, _, _ = select.select([ff.stdout], [], [], 0.5)
        if not r:
            continue
        chunk = ff.stdout.read(65536)
        if not chunk:
            break
        f.write(chunk)
        got += len(chunk)
        if got >= 100_000:
            break
print("bytes", got, "ff_poll", ff.poll())
ff.terminate()
try:
    ff.wait(timeout=3)
except Exception:
    ff.kill()
cam.terminate()
try:
    cam.wait(timeout=3)
except Exception:
    cam.kill()
cam_err.close()
ff_err.close()
PY

ls -la /tmp/mirror_udp.ts 2>/dev/null || true
ffprobe -v error -show_entries stream=codec_name,width,height -of default=nw=1 /tmp/mirror_udp.ts 2>&1 | head -10
echo "--- ff log ---"; tail -20 /tmp/mirror-ff.log
echo "--- cam log ---"; tail -15 /tmp/mirror-cam.log

# restart kiosk for interactive use
cd /home/admin/bhvr-kiosk
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 2
curl -s http://127.0.0.1:8080/api/health; echo
