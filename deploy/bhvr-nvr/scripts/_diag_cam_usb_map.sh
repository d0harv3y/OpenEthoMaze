#!/bin/bash
# Map bhvr-cam* identity ↔ NVR usbN ↔ hub port (after physical port swaps).
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=4 -o StrictHostKeyChecking=accept-new)

echo "=== gadgets $(lsusb | grep -c 1d6b:0104 || echo 0) ==="
lsusb | grep 1d6b:0104 || true
echo
echo "=== hub tree ==="
lsusb -t 2>/dev/null | head -40 || true
echo
echo "=== NVR usbN → hub path + MAC ==="
for d in /sys/class/net/usb[0-9]*; do
  [[ -e "$d" ]] || continue
  name=$(basename "$d")
  mac=$(cat "$d/address" 2>/dev/null || echo '?')
  # device path under USB: .../1-1.1.N/...
  devpath=$(readlink -f "$d/device" 2>/dev/null || true)
  # peel to USB port id (e.g. 1-1.1.3)
  port='?'
  if [[ "$devpath" =~ /(1-[0-9.]+)/ ]]; then
    port="${BASH_REMATCH[1]}"
  fi
  ip=$(ip -4 -br addr show "$name" 2>/dev/null | awk '{print $3}' || true)
  echo "$name mac=$mac port=$port addr=$ip path=$devpath"
done
echo
echo "=== roster (API) ==="
python3 - <<'PY'
import json, urllib.request
h = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=8))
for c in sorted(h.get("cameras") or [], key=lambda x: x.get("id") or ""):
    print(f"{c.get('id')}\tip={c.get('ip')}\tonline={c.get('online')}")
PY
echo
echo "=== probe 192.168.7.0/24 + roster IPs (hostname + cam usb0 mac) ==="
declare -A SEEN=()
probe() {
  local ip=$1
  [[ -n "${SEEN[$ip]:-}" ]] && return
  SEEN[$ip]=1
  if out=$(ssh "${KEY[@]}" "admin@$ip" 'echo HOST=$(hostname); echo MAC=$(cat /sys/class/net/usb0/address 2>/dev/null); echo SERIAL=$(tr -d "\0" </proc/device-tree/serial-number 2>/dev/null)' 2>/dev/null); then
    echo "UP $ip"
    echo "$out" | sed 's/^/  /'
  else
    echo "DOWN $ip"
  fi
}
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  probe "$ip"
done
while IFS=$'\t' read -r cid ip; do
  [[ -n "$ip" ]] || continue
  probe "$ip"
done < <(python3 - <<'PY'
import json, urllib.request
h = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=8))
for c in h.get("cameras") or []:
    if c.get("id") and c.get("ip"):
        print(f"{c['id']}\t{c['ip']}")
PY
)
