#!/bin/bash
# Wait until at least N cams answer SSH (default 3).
set -uo pipefail
NEED="${1:-3}"
for i in $(seq 1 16); do
  echo "try $i need=$NEED"
  out=$(bash "$HOME/deploy/bhvr-nvr/scripts/_diag_cam_serials.sh")
  echo "$out"
  ups=$(echo "$out" | grep -cv DOWN || true)
  gadgets=$(lsusb | grep -c 1d6b:0104 || true)
  echo "ups=$ups gadgets=$gadgets"
  if [[ "$ups" -ge "$NEED" ]]; then
    echo READY
    lsusb -t 2>/dev/null | head -25 || true
    exit 0
  fi
  sleep 5
done
echo NOT_READY
exit 1
