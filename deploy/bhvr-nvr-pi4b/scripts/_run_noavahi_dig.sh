#!/bin/bash
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20)
scp "${KEY[@]}" /tmp/_dig_fps_noavahi.sh admin@192.168.7.27:/tmp/_dig_fps_noavahi.sh
# Prefer ssh -t for sudo password if needed — BatchMode may fail sudo; try anyway
ssh -t "${KEY[@]}" admin@192.168.7.27 'sed -i "s/\r$//" /tmp/_dig_fps_noavahi.sh; bash /tmp/_dig_fps_noavahi.sh' || \
ssh "${KEY[@]}" admin@192.168.7.27 'sed -i "s/\r$//" /tmp/_dig_fps_noavahi.sh; bash /tmp/_dig_fps_noavahi.sh'
