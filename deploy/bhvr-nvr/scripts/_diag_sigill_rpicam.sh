#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10)
ssh "${KEY[@]}" admin@192.168.7.27 'bash -s' <<'EOS'
set -uo pipefail
echo "=== binary ==="
file "$(command -v rpicam-vid)"
ls -la "$(command -v rpicam-vid)"
readelf -A "$(command -v rpicam-vid)" 2>/dev/null | head -20 || true
echo "=== dpkg -S ==="
dpkg -S "$(command -v rpicam-vid)" 2>/dev/null || true
echo "=== half-installed ==="
dpkg -l | awk '/^iU|^iF|^Hi/{print}'
echo "=== ldd missing ==="
ldd "$(command -v rpicam-vid)" 2>&1 | grep -E 'not found|lapack|opencv|Qt' || ldd "$(command -v rpicam-vid)" 2>&1 | head -5
EOS
