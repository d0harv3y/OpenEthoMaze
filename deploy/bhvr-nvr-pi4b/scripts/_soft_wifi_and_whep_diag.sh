#!/bin/bash
# Soft WiFi bounce + WHEP litmus for cam0/cam2 (no NVR reboot).
set +e
echo "=== wifi soft bounce (sudo) ==="
sudo nmcli connection down "netplan-wlan0-WSU-IoT"
sleep 3
sudo nmcli connection up "netplan-wlan0-WSU-IoT"
sleep 5
ip -4 addr show wlan0 | sed -n 's/.*inet /inet /p'
ping -c 2 -W 3 10.248.224.1 | tail -4

echo "=== preview before ==="
ps -ef | grep -E 'rpicam-vid -n -t 0' | grep -v grep | wc -l | xargs -I{} echo rpicam_count={}
curl -sS -m 8 http://127.0.0.1:8080/api/health
echo

KEY=(-o BatchMode=yes -o ConnectTimeout=8 -o IdentitiesOnly=yes -i /home/admin/.ssh/id_ed25519_bhvr)
for ip in 192.168.7.41 192.168.7.31 192.168.7.28; do
  echo "-- $ip --"
  ssh "${KEY[@]}" "admin@$ip" 'hostname; ip -4 route | head -6; ip -4 -br a; echo BROKER; cat /var/lib/bhvr/broker.env 2>/dev/null || echo none' 2>&1 | head -35
done

echo "=== whep cam0 cam2 ==="
for c in bhvr-cam0 bhvr-cam2; do
  code=$(curl -sS -m 180 -o "/tmp/whep_${c}.json" -w "%{http_code}" -X POST "http://127.0.0.1:8080/api/preview/${c}/whep/start")
  echo "$c http=$code $(head -c 200 "/tmp/whep_${c}.json")"
  sleep 2
done
curl -sS -m 8 http://127.0.0.1:8080/api/health | python3 -c 'import sys,json; print("idle", json.load(sys.stdin).get("preview_idle"))'
echo "=== logs cam0 ==="
tail -20 /tmp/bhvr-preview-bhvr-cam0-cam.log 2>/dev/null
tail -20 /tmp/bhvr-preview-bhvr-cam0-remux.log 2>/dev/null
echo "=== logs cam2 ==="
tail -20 /tmp/bhvr-preview-bhvr-cam2-cam.log 2>/dev/null
tail -20 /tmp/bhvr-preview-bhvr-cam2-remux.log 2>/dev/null
