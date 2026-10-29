#!/bin/bash
# Soft-rescue a STALE cam when USB gadget still shows (wired).
# Usage: CAM_ID=bhvr-cam2 bash _soft_rescue_stale_cam.sh
#        or CAM_IP=192.168.7.31 bash ...
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=6 -o StrictHostKeyChecking=accept-new)
CAM_ID="${CAM_ID:-bhvr-cam2}"
CAM_IP="${CAM_IP:-}"

echo "gadgets=$(lsusb | grep -c 1d6b:0104 || true)"
if [[ -z "$CAM_IP" ]]; then
  CAM_IP=$(curl -sS http://127.0.0.1:8080/api/cams | python3 -c '
import sys, json, os
want = os.environ.get("CAM_ID", "bhvr-cam2")
d = json.load(sys.stdin)
for c in d.get("cameras") or []:
    if c.get("id") == want and c.get("ip"):
        print(c["ip"]); break
' 2>/dev/null || true)
fi
# Fallbacks for known wired map (cam2 historically .31)
if [[ -z "$CAM_IP" && "$CAM_ID" == "bhvr-cam2" ]]; then
  CAM_IP=192.168.7.31
fi
echo "target $CAM_ID ip=${CAM_IP:-unknown}"

try_ssh() {
  local ip="$1"
  ssh "${KEY[@]}" "admin@$ip" bash -s <<'REMOTE'
set -euxo pipefail
hostname
ip -br a show usb0 2>/dev/null || true
systemctl is-active bhvr-cam-announce.timer bhvr-cam-usb-gadget.service 2>/dev/null || true
# Refresh gadget + DHCP + announce (does not reboot).
sudo systemctl restart bhvr-cam-usb-gadget.service || true
sleep 2
sudo systemctl restart systemd-networkd 2>/dev/null || true
sudo systemctl restart bhvr-cam-announce.timer || true
sudo systemctl start bhvr-cam-announce.service || true
python3 /usr/local/bin/bhvr-cam-announce || true
REMOTE
}

if [[ -n "$CAM_IP" ]] && try_ssh "$CAM_IP"; then
  echo "SSH_OK $CAM_IP"
else
  echo "SSH_FAIL $CAM_IP — scanning 192.168.7.20-50 for $CAM_ID"
  found=""
  for i in $(seq 20 50); do
    ip="192.168.7.$i"
    if ssh "${KEY[@]}" "admin@$ip" "hostname" 2>/dev/null | grep -qx "$CAM_ID"; then
      found="$ip"
      break
    fi
  done
  if [[ -n "$found" ]]; then
    echo "FOUND $found"
    try_ssh "$found" || exit 1
  else
    echo "NO_SSH — gadget present but no L3/SSH; hard reset or hub power-cycle"
    exit 2
  fi
fi

sleep 2
curl -sS http://127.0.0.1:8080/api/cams | python3 -c '
import sys, json, os
want = os.environ.get("CAM_ID", "bhvr-cam2")
d = json.load(sys.stdin)
for c in d.get("cameras") or []:
    if c.get("id") == want:
        print("roster", {k: c.get(k) for k in ("online", "age_s", "ip", "ts")})
        break
else:
    print("roster_missing")
'
echo RESCUE_DONE
