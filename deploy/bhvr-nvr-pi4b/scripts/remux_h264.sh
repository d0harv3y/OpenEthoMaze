#!/bin/bash
set -euo pipefail
D="${1:-/media/admin/random/bhvr-tests/20260925T214404Z_720p30}"
IN="$D/video.mp4"
OUT="$D/video_playable.mp4"
# Input is annex-B H.264 despite .mp4 suffix
ffmpeg -y -framerate 30 -i "$IN" -c copy "$OUT"
ffprobe -v error -show_entries format=format_name,duration -show_entries stream=codec_name,width,height,nb_frames -of default=nw=1 "$OUT"
ls -la "$IN" "$OUT"
echo "PLAY: $OUT"
