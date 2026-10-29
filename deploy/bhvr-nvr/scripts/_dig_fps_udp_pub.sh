#!/bin/bash
# Run ON cam — publish 720p30 to NVR:15551 for bitrate probe
set -euo pipefail
rpicam-vid -n -t 0 --width 1280 --height 720 --framerate 30 --codec h264 --inline --intra 30 --flush --bitrate 2500000 --denoise cdn_off --buffer-count 2 -o - \
| "$HOME/bin/ffmpeg" -hide_banner -loglevel warning -nostats -use_wallclock_as_timestamps 1 -fflags +genpts+nobuffer+flush_packets -flags low_delay -probesize 32 -analyzeduration 0 -f h264 -i pipe:0 -c copy -f mpegts "udp://192.168.7.1:15551?pkt_size=1316"
