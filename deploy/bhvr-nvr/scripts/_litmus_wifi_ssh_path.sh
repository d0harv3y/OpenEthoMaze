#!/bin/bash
# Fact: can NVR reach cams over WiFi SSH, or only USB?
# Distinguishes AP isolation vs cam sshd/firewall/routing.
set +e
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new
     -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR)

echo "=== NVR addrs ==="
ip -4 -br a

echo "=== discover cams via USB roster / known map ==="
map=$(curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    print(c.get("id",""), c.get("ip",""))
')
echo "$map"

probe_one() {
  local usb_ip="$1"
  echo
  echo "######## USB $usb_ip ########"
  ssh "${KEY[@]}" "admin@$usb_ip" 'bash -s' <<'REMOTE'
set +e
echo "hostname=$(hostname)"
echo "--- addrs ---"
ip -4 -br a
echo "--- routes ---"
ip -4 route | head -8
WIFI=$(ip -4 -o addr show dev wlan0 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)
echo "wifi_ip=${WIFI:-none}"
echo "--- sshd listen ---"
ss -ltnp 2>/dev/null | grep -E ':22\s' || netstat -ltn 2>/dev/null | grep ':22'
echo "--- nft/ufw (if any) ---"
sudo -n nft list ruleset 2>/dev/null | head -5 || true
sudo -n ufw status 2>/dev/null || true
iptables -S 2>/dev/null | head -10 || true
# publish wifi ip for NVR
echo "$WIFI" > /tmp/bhvr_wifi_ip.txt
cat /tmp/bhvr_wifi_ip.txt
REMOTE
  wifi_ip=$(ssh "${KEY[@]}" "admin@$usb_ip" 'cat /tmp/bhvr_wifi_ip.txt 2>/dev/null' | tr -d '\r')
  echo "parsed wifi_ip=${wifi_ip:-empty}"
  if [[ -z "$wifi_ip" || "$wifi_ip" == "none" ]]; then
    echo "NO_WIFI_IP"
    return
  fi

  echo "--- NVR -> ping USB ---"
  ping -c 2 -W 2 "$usb_ip" | tail -3
  echo "--- NVR -> ping WiFi $wifi_ip ---"
  ping -c 3 -W 2 "$wifi_ip" | tail -5
  echo "--- NVR -> TCP 22 WiFi ---"
  if command -v nc >/dev/null; then
    nc -vz -w 3 "$wifi_ip" 22 2>&1
  else
    timeout 3 bash -c "echo >/dev/tcp/$wifi_ip/22" && echo "22 open" || echo "22 closed/fail"
  fi
  echo "--- NVR -> SSH WiFi ---"
  ssh "${KEY[@]}" -o ConnectTimeout=10 "admin@$wifi_ip" 'hostname; echo SSH_WIFI_OK; ip -4 -br a show wlan0' 2>&1 | head -20
  echo "ssh_wifi_exit=$?"

  echo "--- cam: can it ping NVR wlan? ---"
  nvr_wlan=$(ip -4 -o addr show dev wlan0 | awk '{print $4}' | cut -d/ -f1 | head -1)
  ssh "${KEY[@]}" "admin@$usb_ip" "ping -c 2 -W 2 $nvr_wlan; echo cam_to_nvr_exit=\$?" 2>&1 | tail -8
  echo "--- cam: can it TCP 22 to NVR (sanity, nvr may not matter) ---"
  ssh "${KEY[@]}" "admin@$usb_ip" "ping -c 1 -W 2 192.168.7.1; ping -c 1 -W 2 $nvr_wlan" 2>&1 | tail -10
}

# Prefer USB IPs from roster when in 192.168.7.0/24
while read -r id ip; do
  [[ -z "$ip" ]] && continue
  if [[ "$ip" == 192.168.7.* ]]; then
    probe_one "$ip"
  else
    echo "roster $id already wifi ip=$ip — try direct"
    ping -c 2 -W 2 "$ip" | tail -3
    ssh "${KEY[@]}" "admin@$ip" 'hostname; echo DIRECT_WIFI_OK' 2>&1 | head -10
  fi
done <<< "$map"

echo
echo "=== interpretation hints ==="
echo "ping/ssh WiFi FAIL + cam->NVR WiFi ping FAIL => AP blocks station-to-station (isolation) or routing"
echo "ping/ssh WiFi FAIL + cam->NVR WiFi ping OK  => asymmetric / firewall / sshd bind"
echo "TCP 22 closed but ping OK => sshd/firewall on cam"
echo "USB SSH OK + WiFi SSH OK => path fine; earlier failure was transient"
