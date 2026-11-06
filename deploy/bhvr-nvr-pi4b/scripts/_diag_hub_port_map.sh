#!/bin/bash
# Print hub leaf (1-1.1.N) ↔ nvr usbN ↔ cam hostname (via ARP MAC on br-bhvr).
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=4 -o StrictHostKeyChecking=accept-new)

declare -A MAC_TO_HOST=()
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  if out=$(ssh "${KEY[@]}" "admin@$ip" 'hostname; cat /sys/class/net/usb0/address' 2>/dev/null); then
    host=$(echo "$out" | sed -n '1p')
    mac=$(echo "$out" | sed -n '2p' | tr 'A-F' 'a-f')
    MAC_TO_HOST[$mac]=$host
    echo "learned $host ip=$ip mac=$mac"
  fi
done

echo
echo "leaf	nvr_if	cam_host	cam_mac"
for n in 0 1 2 3; do
  leaf=$(readlink -f "/sys/class/net/usb${n}/device" | grep -oE '1-1\.1\.[0-9]+' | head -1 || echo '?')
  # Peer MAC sometimes in neigh after ping through that path — use bridge fdb master
  # Cam MAC is not on NVR iface; match via: which IP answers on which... we only have br.
  # Instead: read CDC iProduct / or just print leaf↔usbN and let operator pair after swap notes.
  echo -n "${leaf}	usb${n}	"
  # Try ethtool / sysfs permanently_peer? 
  peer=""
  if [[ -f /sys/class/net/usb${n}/address ]]; then
    :
  fi
  # Heuristic: after ping all cams, fdb shows master usbN for cam MAC
  for mac in "${!MAC_TO_HOST[@]}"; do
    if bridge fdb show br br-bhvr 2>/dev/null | grep -qi "$mac" | grep -q "usb${n}"; then
      echo -n "${MAC_TO_HOST[$mac]}	$mac"
    fi
  done
  # fdb line format: <mac> dev usbN master br-bhvr
  hit=$(bridge fdb show 2>/dev/null | awk -v ifc="usb${n}" 'BEGIN{IGNORECASE=1} $3==ifc || $0 ~ ("dev " ifc " ") {print $1; exit}')
  if [[ -n "$hit" ]]; then
    hmac=$(echo "$hit" | tr 'A-F' 'a-f')
    echo "${MAC_TO_HOST[$hmac]:-?}	$hmac"
  else
    echo "?	?"
  fi
done

echo
echo "=== bridge fdb (cam MACs) ==="
bridge fdb show 2>/dev/null | grep -iE '02:27:eb' || true
