#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  if out=$(ssh "${KEY[@]}" "admin@$ip" 'hostname; tr -d "\0" </proc/device-tree/serial-number' 2>/dev/null); then
    echo "$ip $out" | tr '\n' ' '
    echo
  else
    echo "$ip DOWN"
  fi
done
