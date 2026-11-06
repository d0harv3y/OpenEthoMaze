#!/bin/bash
# Remove half-installed / armv7-tainted packages from Pi Zero after bad offline dpkg.
# Run ON CAM with sudo: sudo bash _recover_cam1_dpkg_mess.sh
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root: sudo bash $0" >&2
  exit 1
fi

# Meta + encoder stack + ffmpeg + known armv7/debian-pulled deps from the bad bake.
PKGS=(
  ffmpeg
  rpicam-apps
  rpicam-apps-encoder
  rpicam-apps-preview
  rpicam-apps-opencv-postprocess
  libavdevice61
  libavfilter10
  libavformat61
  libavcodec61
  libavutil59
  libswresample5
  libswscale8
  libpostproc58
  libopencv-calib3d410
  libopencv-objdetect410
  libopencv-dnn410
  libopencv-features2d410
  libopencv-flann410
  libopencv-imgproc410
  libopencv-core410
  libpocketsphinx3
  libsphinxbase3t64
  liblapack3
  libgfortran5
  libqt5widgets5t64
  libqt5gui5t64
  libqt5dbus5t64
  libqt5network5t64
  libqt5core5t64
  librsvg2-2
  libpangoft2-1.0-0
  libpangocairo-1.0-0
  libpango-1.0-0
  fontconfig
  fontconfig-config
  fonts-dejavu-core
  fonts-dejavu-mono
)

echo "Removing broken packages (keeping rpicam-apps-core)…"
dpkg --remove --force-depends --force-remove-reinstreq "${PKGS[@]}" || true
dpkg --configure -a || true

echo "=== remaining half-installed ==="
dpkg -l | awk '/^iU|^iF|^Hi/{print}' || echo '(none)'
echo "=== rpicam smoke ==="
command -v rpicam-vid
timeout 4 rpicam-vid -n -t 2000 --width 640 --height 480 --framerate 15 --codec h264 --inline -o /tmp/recover.h264
ls -la /tmp/recover.h264
echo "DONE — use ~/bin/ffmpeg for Mode 1 (static). Do NOT dpkg the NVR-fetched Debian armhf tree onto Zero."
