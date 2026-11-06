#!/bin/bash
pgrep -af 'usb-push|192.168.7..*bash -s' | head -15 || true
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  echo -n "$ip: "
  out=$(ssh "${KEY[@]}" "admin@$ip" 'ps -eo pid,cmd | grep -E "sudo|timeout|tee" | grep -v grep | head -2' 2>/dev/null || echo unreachable)
  echo "$out"
done
