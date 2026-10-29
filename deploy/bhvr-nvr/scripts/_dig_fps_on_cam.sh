#!/bin/bash
# Run ON cam1
set -euxo pipefail
FF="$HOME/bin/ffmpeg"
test -x "$FF"

count_frames() {
  local f="$1"
  # Count access-unit approx: number of AUD or IDR/non-IDR NAL starts (0x000001 + type).
  python3 - "$f" <<'PY'
import sys
data = open(sys.argv[1], "rb").read()
# annex-B start codes
i = 0
nals = 0
slices = 0
while True:
    j = data.find(b"\x00\x00\x00\x01", i)
    k = data.find(b"\x00\x00\x01", i)
    if j < 0 and k < 0:
        break
    if j < 0:
        pos = k
        sc = 3
    elif k < 0 or j < k:
        pos = j
        sc = 4
    else:
        pos = k
        sc = 3
    if pos + sc >= len(data):
        break
    nal_type = data[pos + sc] & 0x1F
    nals += 1
    if nal_type in (1, 5):  # non-IDR / IDR slice
        slices += 1
    i = pos + sc + 1
print(f"nals={nals} slices={slices}")
PY
}

echo "=== list cameras ==="
rpicam-vid --list-cameras 2>&1 | head -60

echo "=== A default 1280x720@30 for 5s ==="
rm -f /tmp/fps_a.h264
timeout 7 rpicam-vid -n -t 5000 --width 1280 --height 720 --framerate 30 --codec h264 --inline --intra 30 --flush --bitrate 2500000 --denoise cdn_off --buffer-count 2 -o /tmp/fps_a.h264 >/tmp/fps_a.log 2>&1 || true
wc -c /tmp/fps_a.h264
count_frames /tmp/fps_a.h264
grep -E 'Mode selection|Selected sensor|frames|Dropped|Stream configuration|SGBRG' /tmp/fps_a.log | head -30
"$FF" -hide_banner -loglevel info -f h264 -i /tmp/fps_a.h264 -c copy -f null - 2>&1 | tail -15

echo "=== B --mode 1296:972:10:P 1280x720@30 5s ==="
rm -f /tmp/fps_b.h264
timeout 7 rpicam-vid -n -t 5000 --mode 1296:972:10:P --width 1280 --height 720 --framerate 30 --codec h264 --inline --intra 30 --flush --bitrate 2500000 --denoise cdn_off --buffer-count 2 -o /tmp/fps_b.h264 >/tmp/fps_b.log 2>&1 || true
wc -c /tmp/fps_b.h264
count_frames /tmp/fps_b.h264
grep -E 'Mode selection|Selected sensor|frames|Dropped|Stream configuration' /tmp/fps_b.log | head -20

echo "=== C 640x480@30 5s ==="
rm -f /tmp/fps_c.h264
timeout 7 rpicam-vid -n -t 5000 --width 640 --height 480 --framerate 30 --codec h264 --inline --intra 30 --flush --bitrate 2500000 --denoise cdn_off --buffer-count 2 -o /tmp/fps_c.h264 >/tmp/fps_c.log 2>&1 || true
wc -c /tmp/fps_c.h264
count_frames /tmp/fps_c.h264
grep -E 'Mode selection|Selected sensor|frames|Dropped|Stream configuration' /tmp/fps_c.log | head -20

echo "=== D 1280x720@15 5s (control) ==="
rm -f /tmp/fps_d.h264
timeout 7 rpicam-vid -n -t 5000 --width 1280 --height 720 --framerate 15 --codec h264 --inline --intra 15 --flush --bitrate 2500000 --denoise cdn_off --buffer-count 2 -o /tmp/fps_d.h264 >/tmp/fps_d.log 2>&1 || true
wc -c /tmp/fps_d.h264
count_frames /tmp/fps_d.h264

echo "=== E verbose level 2 one short run ==="
timeout 4 rpicam-vid -n -t 2000 --width 1280 --height 720 --framerate 30 --codec h264 --inline --bitrate 2500000 -o /tmp/fps_e.h264 --verbose 2>/tmp/fps_e.log || true
grep -iE 'fps|frame|drop|rate|mode|sensor' /tmp/fps_e.log | head -40

echo CAM_DIG_DONE
