#!/bin/bash
set +e
echo "=== roster / idle ==="
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import sys,json
for c in json.load(sys.stdin).get("cameras",[]):
    ip=c.get("ip") or ""
    mode="usb" if ip.startswith("192.168.7.") else ("wifi" if ip.startswith("10.") else "other")
    print(c["id"], "online="+str(c.get("online")), "ip="+ip, "announce_mode="+mode, "age="+str(c.get("age_s")))
'
curl -sS -m 8 http://127.0.0.1:8080/api/health | python3 -c 'import sys,json; print("preview_idle", json.load(sys.stdin).get("preview_idle"))'
echo "gadgets=$(lsusb | grep -c 1d6b:0104 || true)"
ip neigh show dev br-bhvr
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=6)
for ip in 192.168.7.31 192.168.7.28 192.168.7.41; do
  echo "== $ip =="
  ssh "${KEY[@]}" "admin@$ip" 'hostname; ip -4 route | head -4; ip -4 -br a' 2>&1 | head -15
done
