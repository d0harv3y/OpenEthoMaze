#!/bin/bash
# Deploy announce backhaul + kiosk WiFi SSH path. Restart kiosk (drops idle WHEP).
set +e
sed -i 's/\r$//' /tmp/announce_mqtt.py /tmp/_litmus_mode_switch_cam0.sh 2>/dev/null
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)

echo "=== push announce to USB cams ==="
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  echo "-- $ip --"
  scp "${KEY[@]}" /tmp/announce_mqtt.py "admin@$ip:/tmp/announce_mqtt.py" 2>&1 | tail -2
  ssh "${KEY[@]}" "admin@$ip" 'bash -s' <<'REMOTE'
set -e
sudo tee /usr/local/bin/bhvr-cam-announce >/dev/null </tmp/announce_mqtt.py
sudo chmod 755 /usr/local/bin/bhvr-cam-announce
python3 /usr/local/bin/bhvr-cam-announce || true
REMOTE
done

echo "=== restart kiosk ==="
cd "$HOME/bhvr-kiosk"
pkill -f 'uvicorn app.main:app' || true
sleep 2
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>uvicorn.log 2>&1 &
sleep 3
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    print(c.get("id"), "ip="+str(c.get("ip")), "link="+str(c.get("link")), "ips="+str(c.get("ips")))
'
echo DEPLOY_MODE_SWITCH_DONE
