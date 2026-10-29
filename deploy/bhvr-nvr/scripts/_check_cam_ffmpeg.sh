#!/bin/bash
set -eu
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
for ip in 10.248.229.141 10.248.233.15 10.248.235.74; do
  echo "=== $ip ==="
  ssh "${KEY[@]}" "admin@$ip" 'ls -la ~/bin/ffmpeg 2>&1; command -v ffmpeg; echo PATH=$PATH' 2>&1 | head -8 || echo FAIL
done
