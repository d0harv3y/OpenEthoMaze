#!/bin/bash
# What can rpicam-vid emit without a cam-side ffmpeg remux?
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
IP="${1:-192.168.7.27}"
ssh "${KEY[@]}" "admin@$IP" 'rpicam-vid --help 2>&1' | grep -iE 'libav|mpeg|udp|rtsp|output|codec|inline|flush|intra|bitrate|save-pts|nopreview' | head -50
echo '==== version ===='
ssh "${KEY[@]}" "admin@$IP" 'rpicam-vid --version 2>&1 | head -5; ls ~/bin/ffmpeg; ~/bin/ffmpeg -hide_banner -encoders 2>/dev/null | grep -i h264 | head; ~/bin/ffmpeg -hide_banner -muxers 2>/dev/null | grep -iE "mpegts|rtsp" | head'
