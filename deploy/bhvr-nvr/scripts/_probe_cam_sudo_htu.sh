#!/bin/bash
# Probe which cams have NOPASSWD tee (firstboot sudoers) + current htu21d size.
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)
echo "=== roster ==="
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json, sys
for c in json.load(sys.stdin).get("cameras", []):
    print(c.get("id"), c.get("ip"), "online="+str(c.get("online")),
          "temp=", c.get("temp_c"), "link=", c.get("link"))
'
echo "=== cams ==="
for ip in 192.168.7.27 192.168.7.31 192.168.7.28; do
  echo "======== $ip ========"
  ssh "${KEY[@]}" "admin@$ip" bash -s <<'REMOTE' || echo "SSH_FAIL $ip"
hostname
ls /etc/sudoers.d/ 2>&1
if sudo -n /usr/bin/tee /dev/null </dev/null 2>/dev/null; then echo TEE_NOPASS_OK; else echo TEE_NOPASS_NO; fi
ls -la /usr/local/lib/bhvr/htu21d.py /usr/local/bin/bhvr-cam-htu21d 2>&1 || true
wc -c /usr/local/lib/bhvr/htu21d.py 2>&1 || true
grep -E '^def ' /usr/local/lib/bhvr/htu21d.py 2>/dev/null | head -8 || true
REMOTE
done
