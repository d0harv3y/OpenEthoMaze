#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new)
LOG=$(ls -dt /tmp/litmus_unplug_bhvr-cam2_* 2>/dev/null | head -1)
echo "log=$LOG"
[[ -n "$LOG" ]] && {
  echo "=== result ==="; cat "$LOG/result.txt" 2>/dev/null
  echo "=== cam_wifi_announce.log ==="; cat "$LOG/cam_wifi_announce.log" 2>/dev/null
  echo "=== mqtt.log ==="; cat "$LOG/mqtt.log" 2>/dev/null
  echo "=== preflight_cam ==="; cat "$LOG/preflight_cam.txt" 2>/dev/null
}
echo "=== roster ==="
bash /tmp/_snap_roster.sh 2>/dev/null || true
echo "=== ping wifi 10.248.229.141 ==="
ping -c 3 -W 2 10.248.229.141 2>&1 | tail -6
echo "=== ssh wifi ==="
ssh "${KEY[@]}" admin@10.248.229.141 bash -s <<'REMOTE' || { echo WIFI_SSH_FAIL; exit 0; }
set +e
hostname; date -u +%H:%M:%SZ
ip -br a
echo "--- routes ---"
ip route
echo "--- broker ---"
cat /var/lib/bhvr/broker.env
echo "--- announce markers ---"
grep -c _mqtt_publish_failover /usr/local/bin/bhvr-cam-announce
grep -c _drop_stale_usb_routes /usr/local/bin/bhvr-cam-announce
echo "--- timer ---"
systemctl is-active bhvr-cam-announce.timer
systemctl list-timers bhvr-cam-announce.timer --no-pager 2>&1 | head -5
journalctl -u bhvr-cam-announce.service -n 30 --no-pager 2>&1
echo "--- manual announce ---"
python3 /usr/local/bin/bhvr-cam-announce 2>&1
echo "--- tcp probes ---"
python3 - <<'PY'
import socket, subprocess
from pathlib import Path

def tcp(h, src=None, t=2.0):
    s=socket.socket(); s.settimeout(t)
    try:
        if src: s.bind((src,0))
        s.connect((h,1883)); return "OK"
    except OSError as e:
        return f"{type(e).__name__}:{e}"
    finally:
        s.close()

wifi=None
for line in subprocess.check_output(["ip","-4","-o","a","show","dev","wlan0"],text=True).splitlines():
    p=line.split()
    if len(p)>=4 and "/" in p[3]:
        wifi=p[3].split("/")[0]
print("wifi", wifi)
print("carrier", Path("/sys/class/net/usb0/carrier").read_text().strip() if Path("/sys/class/net/usb0/carrier").is_file() else None)
print("tcp 192.168.7.1 no-bind", tcp("192.168.7.1"))
print("tcp 10.248.238.22 no-bind", tcp("10.248.238.22"))
print("tcp 10.248.238.22 src=wifi", tcp("10.248.238.22", wifi))
for h in ("192.168.7.1","10.248.238.22"):
    print("route get", h, ":", subprocess.check_output(["ip","route","get",h],text=True).strip())
PY
REMOTE
