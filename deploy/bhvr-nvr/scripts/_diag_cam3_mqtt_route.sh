#!/bin/bash
# Why announce MQTT times out on WiFi after USB unplug (or dual-homed).
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new)
WIFI=10.248.235.74

echo "=== NVR mosquitto listen ==="
ss -lntp | grep 1883 || netstat -lntp 2>/dev/null | grep 1883 || true
systemctl is-active mosquitto 2>/dev/null || true

echo "=== litmus log tail ==="
ls -dt /tmp/litmus_unplug_bhvr-cam3_* 2>/dev/null | head -1 | while read -r d; do
  echo "dir=$d"
  tail -30 "$d/cam_wifi_announce.log" 2>/dev/null || true
done

echo "=== cam3 via WiFi $WIFI ==="
ssh "${KEY[@]}" "admin@$WIFI" bash -s <<'REMOTE'
set +e
hostname
date -u +%Y-%m-%dT%H:%M:%SZ
ip -br a
echo "--- routes ---"
ip route
echo "--- broker ---"
cat /var/lib/bhvr/broker.env
echo "--- link_state ---"
cat /var/lib/bhvr/link_state.json 2>/dev/null; cat ~/.cache/bhvr/link_state.json 2>/dev/null
echo "--- carrier/tcp ---"
echo "carrier=$(cat /sys/class/net/usb0/carrier 2>/dev/null)"
python3 - <<'PY'
import socket, time
from pathlib import Path

def tcp(h, p=1883, t=2.0):
    t0 = time.time()
    try:
        socket.create_connection((h, p), timeout=t).close()
        return True, round(time.time() - t0, 3)
    except OSError as e:
        return False, f"{type(e).__name__}:{e}"

for h in ("192.168.7.1", "10.248.238.22", "127.0.0.1"):
    ok, info = tcp(h)
    print(f"tcp {h}:1883 -> {ok} {info}")

# Which src/route would be used?
import subprocess
for h in ("192.168.7.1", "10.248.238.22"):
    try:
        out = subprocess.check_output(["ip", "route", "get", h], text=True).strip()
    except Exception as e:
        out = str(e)
    print(f"route get {h}: {out}")
PY
echo "--- announce once ---"
python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -20
echo "--- markers ---"
grep -n "_usb_link_usable\|MQTT_BROKER_WIFI\|USB down\|_mqtt_publish\|_load_broker" /usr/local/bin/bhvr-cam-announce | head -40
REMOTE
