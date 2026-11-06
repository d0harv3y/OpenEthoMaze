#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
echo "gadgets=$(lsusb | grep -c 1d6b:0104 || true)"
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  if host=$(ssh "${KEY[@]}" "admin@$ip" hostname 2>/dev/null); then
    echo "UP $ip $host"
  else
    echo "DOWN $ip"
  fi
done
