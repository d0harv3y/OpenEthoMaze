#!/bin/bash
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20)
scp "${KEY[@]}" /tmp/_dig_fps_pts.sh admin@192.168.7.27:/tmp/_dig_fps_pts.sh
ssh "${KEY[@]}" admin@192.168.7.27 'sed -i "s/\r$//" /tmp/_dig_fps_pts.sh; killall -9 rpicam-vid 2>/dev/null || true; killall -9 ffmpeg 2>/dev/null || true; bash /tmp/_dig_fps_pts.sh'
