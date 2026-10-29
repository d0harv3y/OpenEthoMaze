#!/bin/bash
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=6 -o StrictHostKeyChecking=accept-new)
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  echo "=== $ip ==="
  ssh "${KEY[@]}" "admin@$ip" 'hostname; command -v ffmpeg; ls -la ~/bin/ffmpeg 2>/dev/null || true; tail -40 /tmp/fanout_pub.log 2>/dev/null || echo no_pub_log' || echo SSH_FAIL
done
echo "=== scale logs ==="
tail -10 /tmp/fanout_bhvr-cam0_scale.log || true
