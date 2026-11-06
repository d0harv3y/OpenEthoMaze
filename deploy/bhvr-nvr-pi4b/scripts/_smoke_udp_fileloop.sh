#!/bin/bash
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15)

scp "${KEY[@]}" /tmp/_cam_start_fileloop_udp.sh admin@192.168.7.27:/tmp/
ssh "${KEY[@]}" admin@192.168.7.27 'sed -i "s/\r$//" /tmp/_cam_start_fileloop_udp.sh; bash /tmp/_cam_start_fileloop_udp.sh'
bash /tmp/_nvr_listen_udp.sh
ssh "${KEY[@]}" admin@192.168.7.27 'pkill -9 -f "ffmpeg.*15550" 2>/dev/null || true; echo stopped'
