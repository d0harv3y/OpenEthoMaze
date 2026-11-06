#!/bin/bash
# Publish live HW H.264 as MPEG-TS over UDP (one focus stream per cam).
# Usage: live_udp_mpegts.sh <nvr_host> <udp_port> [width] [height] [fps] [bitrate_kbps] [buffer_count] [sensor_mode]
# sensor_mode: auto | 1296:972 | 1920:1080 | 640:480  (OV5647 / Pi Cam v1-class)
set -euo pipefail

NVR_HOST="${1:?nvr host}"
UDP_PORT="${2:?udp port}"
WIDTH="${3:-640}"
HEIGHT="${4:-480}"
FPS="${5:-15}"
BITRATE_KBPS="${6:-800}"
BUF="${7:-2}"
SENSOR_MODE="${8:-auto}"
BITRATE=$((BITRATE_KBPS * 1000))
INTRA="${FPS}"

MODE_ARGS=()
case "${SENSOR_MODE}" in
  ""|auto|default|libcamera) ;;
  *)
    # libcamera wants W:H:bitdepth:P
    MODE_ARGS=(--mode "${SENSOR_MODE}:10:P")
    ;;
esac

command -v rpicam-vid >/dev/null
# Prefer user-local static binary (USB push without root) then PATH.
FFMPEG_BIN=""
for c in "${HOME}/bin/ffmpeg" /usr/local/bin/ffmpeg ffmpeg; do
  if [[ "$c" == ffmpeg ]]; then
    command -v ffmpeg >/dev/null && FFMPEG_BIN=$(command -v ffmpeg) && break
  elif [[ -x "$c" ]]; then
    FFMPEG_BIN="$c"
    break
  fi
done
[[ -n "$FFMPEG_BIN" ]] || {
  echo "ffmpeg not found (tried ~/bin/ffmpeg, /usr/local/bin/ffmpeg, PATH)" >&2
  exit 1
}

# Do not pkill this script by name (nohup races). Stop prior encoders only.
pkill -INT rpicam-vid 2>/dev/null || true
pkill -f "ffmpeg.*udp://${NVR_HOST}:${UDP_PORT}" 2>/dev/null || true
sleep 0.2

# Pipe annex-B into MPEG-TS over UDP (pkt_size fits typical WiFi MTU path).
# genpts: annex-B from rpicam has no timing; without it MSE/mpegts.js stays black.
exec stdbuf -o0 rpicam-vid -n -t 0 \
  "${MODE_ARGS[@]}" \
  --width "${WIDTH}" --height "${HEIGHT}" \
  --framerate "${FPS}" --codec h264 --inline \
  --intra "${INTRA}" --flush \
  --bitrate "${BITRATE}" --denoise cdn_off \
  --buffer-count "${BUF}" -o - \
| "$FFMPEG_BIN" -hide_banner -loglevel warning -nostats \
    -use_wallclock_as_timestamps 1 \
    -fflags +genpts+nobuffer+flush_packets -flags low_delay -avioflags direct \
    -probesize 32 -analyzeduration 0 \
    -f h264 -i pipe:0 -c copy \
    -muxdelay 0 -muxpreload 0 -flush_packets 1 \
    -f mpegts "udp://${NVR_HOST}:${UDP_PORT}?pkt_size=1316&fifo_size=1000000&overrun_nonfatal=1"
