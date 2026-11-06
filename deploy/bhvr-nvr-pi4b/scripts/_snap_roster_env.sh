#!/bin/bash
set +e
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    print(
        c.get("id"),
        "online="+str(c.get("online")),
        "age="+str(c.get("age_s")),
        "temp="+str(c.get("temp_c")),
        "rh="+str(c.get("rh_pct")),
        "env="+str(bool(c.get("env"))),
        "ip="+str(c.get("ip")),
        "link="+str(c.get("link")),
    )
'
echo "--- last mqtt (cam2/3) ---"
mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/bhvr-cam2/state' -C 1 -W 2 -v 2>&1 | head -1
mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/bhvr-cam3/state' -C 1 -W 2 -v 2>&1 | head -1

KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
for ip in 192.168.7.31 192.168.7.28; do
  echo "=== $ip ==="
  ssh "${KEY[@]}" "admin@$ip" 'hostname; ls /usr/local/lib/bhvr/htu21d.py /usr/local/bin/htu21d.py 2>/dev/null; ls /dev/i2c-1 2>/dev/null; python3 -c "from htu21d import window_stats; print(window_stats())" 2>&1 | tail -5; python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -2' 2>&1 | head -20
done
