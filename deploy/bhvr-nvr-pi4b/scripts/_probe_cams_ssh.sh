#!/bin/bash
set -euo pipefail
python3 - <<'PY'
import json, urllib.request, subprocess, os
h = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=8))
key = [
    "-i", os.path.expanduser("~/.ssh/id_ed25519_bhvr"),
    "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
]
for c in h.get("cameras") or []:
    cid, ip = c.get("id"), c.get("ip")
    online, age = c.get("online"), c.get("age_s")
    try:
        out = subprocess.check_output(
            ["ssh", *key, f"admin@{ip}",
             "hostname; echo rpicam=$(pgrep -c rpicam-vid || echo 0)"],
            text=True, stderr=subprocess.STDOUT, timeout=10,
        )
        print(f"{cid} {ip} mqtt_online={online} age={age} SSH_OK {out.strip().replace(chr(10), ' | ')}")
    except Exception as e:
        print(f"{cid} {ip} mqtt_online={online} age={age} SSH_FAIL {type(e).__name__}")
PY
