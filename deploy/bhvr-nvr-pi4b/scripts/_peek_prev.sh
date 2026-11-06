#!/bin/bash
set -euo pipefail
python3 - <<'PY'
d = open("/tmp/udp-prev.bin", "rb").read()
print(f"bytes={len(d)} sync0=0x{d[0]:02x} head={d[:16].hex()}")
PY
curl -sS http://127.0.0.1:8080/api/health
echo
curl -sS http://127.0.0.1:8080/api/cams
echo
