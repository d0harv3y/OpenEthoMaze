#!/bin/bash
# Timed USB→WiFi failover litmus (run on NVR, cam still on USB).
#
# Usage:
#   bash _litmus_unplug_failover.sh bhvr-cam3
#   bash _litmus_unplug_failover.sh bhvr-cam3 192.168.7.28
#
# Flow:
#   1) Preflight (ONLINE·USB, ips.usb+ips.wifi, MQTT_BROKER_WIFI, WiFi MQTT OK)
#   2) Open WiFi SSH log (announce loop) BEFORE unplug
#   3) You unplug when prompted; we timestamp MQTT retain + roster every 1s
#   4) Pass if link=wifi + online within 60s
set -euo pipefail
CAM_ID="${1:-bhvr-cam3}"
USB_IP_ARG="${2:-}"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)
LOG=/tmp/litmus_unplug_${CAM_ID}_$(date +%Y%m%dT%H%M%S)
mkdir -p "$LOG"
PASS_S="${LITMUS_PASS_S:-60}"

roster_row() {
  curl -sS -m 5 http://127.0.0.1:8080/api/cams | python3 -c '
import json, sys
want = sys.argv[1]
for c in json.load(sys.stdin).get("cameras", []):
    if c.get("id") == want:
        print(json.dumps(c))
        break
else:
    print("{}")
' "$CAM_ID"
}

# Emit KEY=value lines for eval — all values shlex-quoted (dicts as JSON).
parse_preflight() {
  python3 -c '
import json, shlex, sys
c = json.loads(sys.argv[1] or "{}")
arg_usb = sys.argv[2] if len(sys.argv) > 2 else ""
ips = c.get("ips") or {}
usb = arg_usb or ips.get("usb") or (c.get("ip") if c.get("link") == "usb" else "") or ""
wifi = ips.get("wifi") or (c.get("ip") if c.get("link") == "wifi" else "") or ""
online = "1" if c.get("online") else "0"
print("USB_IP=" + shlex.quote(str(usb)))
print("WIFI_IP=" + shlex.quote(str(wifi)))
print("LINK=" + shlex.quote(str(c.get("link") or "")))
print("ONLINE=" + shlex.quote(online))
' "$1" "$2"
}

parse_poll() {
  python3 -c '
import json, shlex, sys
c = json.loads(sys.argv[1] or "{}")
online = "1" if c.get("online") else "0"
print("R_LINK=" + shlex.quote(str(c.get("link") or "")))
print("R_ONLINE=" + shlex.quote(online))
print("R_IP=" + shlex.quote(str(c.get("ip") or "")))
print("R_AGE=" + shlex.quote(str(c.get("age_s") if c.get("age_s") is not None else "")))
print("R_IPS=" + shlex.quote(json.dumps(c.get("ips") or {}, separators=(",", ":"))))
' "$1"
}

fail() { echo "FAIL: $*" | tee -a "$LOG/result.txt"; exit 1; }

echo "log dir: $LOG"
echo "=== preflight roster ==="
ROW=$(roster_row)
echo "$ROW" | tee "$LOG/preflight_roster.json" | python3 -m json.tool
eval "$(parse_preflight "$ROW" "$USB_IP_ARG")"

[[ "$ONLINE" == "1" ]] || fail "cam not ONLINE before unplug"
[[ "$LINK" == "usb" ]] || fail "want link=usb before unplug (got $LINK)"
[[ -n "$USB_IP" ]] || fail "no USB IP"
[[ -n "$WIFI_IP" ]] || fail "no WiFi IP in roster ips — associate wlan0 + wait announce before timing"

echo "=== preflight SSH $USB_IP ==="
ssh "${KEY[@]}" "admin@$USB_IP" bash -s <<'REMOTE' | tee "$LOG/preflight_cam.txt"
set -euo pipefail
hostname
ip -br a
echo "--- broker.env ---"
cat /var/lib/bhvr/broker.env
grep -q MQTT_BROKER_WIFI /var/lib/bhvr/broker.env
grep -q _usb_link_usable /usr/local/bin/bhvr-cam-announce \
  || grep -q 'USB down' /usr/local/bin/bhvr-cam-announce \
  || { echo "WARN: announce may lack zombie/WiFi broker failover"; }
python3 - <<'PY'
import socket
from pathlib import Path

def tcp(h, p=1883, t=1.0):
    try:
        socket.create_connection((h, p), timeout=t).close()
        return True
    except OSError:
        return False

carrier = Path("/sys/class/net/usb0/carrier")
print("usb0_carrier", carrier.read_text().strip() if carrier.is_file() else None)
print("usb_mqtt", tcp("192.168.7.1"))
wifi = None
for line in open("/var/lib/bhvr/broker.env"):
    if line.startswith("MQTT_BROKER_WIFI="):
        wifi = line.split("=", 1)[1].strip()
print("wifi_broker", wifi, "ok" if wifi and tcp(wifi) else "FAIL")
if not wifi or not tcp(wifi):
    raise SystemExit("WiFi MQTT broker not reachable from cam — Invite first")
PY
REMOTE

echo "=== start WiFi-side announce watch (before unplug) ==="
ssh "${KEY[@]}" -o ConnectTimeout=20 "admin@$WIFI_IP" \
  'while true; do printf "%s " "$(date -u +%H:%M:%S)"; python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tr "\n" " "; echo; sleep 2; done' \
  >"$LOG/cam_wifi_announce.log" 2>&1 &
WATCH_PID=$!

(
  mosquitto_sub -h 127.0.0.1 -t "bhvr/cam/${CAM_ID}/state" -v 2>/dev/null \
    | while IFS= read -r line; do echo "$(date -u +%H:%M:%S) $line"; done
) >"$LOG/mqtt.log" &
MQTT_PID=$!
trap 'kill $WATCH_PID $MQTT_PID 2>/dev/null || true' EXIT

echo
echo "************************************************************"
echo "  Prefail checks passed for $CAM_ID"
echo "  USB=$USB_IP  WiFi=$WIFI_IP"
echo "  UNPLUG the USB data cable NOW, then press Enter here."
echo "************************************************************"
read -r _

T0=$(date +%s)
T0H=$(date -u +%H:%M:%S)
echo "T0_unplug=$T0H" | tee "$LOG/t0.txt"
echo "polling roster + ICMP to WiFi IP every 1s (pass if link=wifi && online within ${PASS_S}s)..."
echo "If ping to $WIFI_IP dies, this is POWER/WiFi drop — not announce hysteresis."

T_WIFI=""
T_ONLINE_WIFI=""
PING_DEAD_S=""
while true; do
  now=$(date +%s)
  elapsed=$((now - T0))
  row=$(roster_row)
  eval "$(parse_poll "$row")"
  if ping -c 1 -W 1 "$WIFI_IP" >/dev/null 2>&1; then
    ping_st=ok
  else
    ping_st=DEAD
    if [[ -z "$PING_DEAD_S" ]]; then
      PING_DEAD_S=$elapsed
      echo "  >> WiFi ICMP DEAD at +${PING_DEAD_S}s (cam left the air / lost power)"
    fi
  fi
  line=$(printf "+%3ds link=%-4s online=%-5s age=%s ip=%s ping=%s ips=%s" \
    "$elapsed" "$R_LINK" "$R_ONLINE" "$R_AGE" "$R_IP" "$ping_st" "$R_IPS")
  echo "$line" | tee -a "$LOG/poll.txt"

  if [[ -z "$T_WIFI" && "$R_LINK" == "wifi" ]]; then
    T_WIFI=$elapsed
    echo "  >> first link=wifi at +${T_WIFI}s"
  fi
  if [[ -z "$T_ONLINE_WIFI" && "$R_LINK" == "wifi" && "$R_ONLINE" == "1" ]]; then
    T_ONLINE_WIFI=$elapsed
    echo "  >> ONLINE·WiFi at +${T_ONLINE_WIFI}s"
    break
  fi
  if (( elapsed >= PASS_S )); then
    echo "TIMEOUT ${PASS_S}s" | tee -a "$LOG/result.txt"
    echo "--- last cam wifi announce log ---"
    tail -20 "$LOG/cam_wifi_announce.log" || true
    echo "--- last mqtt ---"
    tail -10 "$LOG/mqtt.log" || true
    if [[ -n "$PING_DEAD_S" ]]; then
      fail "WiFi ICMP died at +${PING_DEAD_S}s — cam powered off or left AP (not MQTT failover). Keep 5V on unplug, then retest. See $LOG"
    fi
    fail "no ONLINE·WiFi within ${PASS_S}s (announce/MQTT stuck; WiFi ICMP stayed up). See $LOG"
  fi
  sleep 1
done

kill $WATCH_PID $MQTT_PID 2>/dev/null || true
echo "PASS ONLINE·WiFi in ${T_ONLINE_WIFI}s (first wifi link ${T_WIFI}s)" | tee "$LOG/result.txt"
echo "artifacts: $LOG"
