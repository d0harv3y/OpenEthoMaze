#!/bin/bash
# First-boot installer for bhvr-cam. Invoked once via cmdline.txt:
#   systemd.run=/boot/firmware/bhvr-firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target
#
# Payload lives on the FAT boot partition as bhvr-cam/ (copied by apply-to-boot.ps1).
# Always clears the cmdline hook so a failed install does not loop forever.
set -uo pipefail

exec >/boot/firmware/bhvr-firstrun.log 2>&1 || exec >/boot/bhvr-firstrun.log 2>&1 || true
echo "bhvr-firstrun start $(date -u -Iseconds)"

cleanup_cmdline() {
  local f
  for f in /boot/firmware/cmdline.txt /boot/cmdline.txt; do
    if [[ -f "$f" ]]; then
      echo "cleaning $f"
      sed -i -e 's| systemd.run=[^ ]*||g' \
             -e 's| systemd.run_success_action=[^ ]*||g' \
             -e 's| systemd.unit=kernel-command-line.target||g' \
             "$f"
      return 0
    fi
  done
}

# Comprehensive net dump onto boot FAT (Windows-readable).
write_net_report() {
  local status="$1"
  local result="$2"
  local waited="$3"
  local ip="${4:-}"
  local def_via=""
  local def_dev=""
  local def_line=""

  def_line="$(ip -4 route show default 2>/dev/null | head -1 || true)"
  if [[ -n "$def_line" ]]; then
    def_via="$(awk '/via/ {for(i=1;i<=NF;i++) if($i=="via"){print $(i+1); exit}}' <<<"$def_line")"
    def_dev="$(awk '/dev/ {for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}' <<<"$def_line")"
  fi

  {
    echo "bhvr-net-status $(date -u -Iseconds)"
    echo "hostname=$(hostname 2>/dev/null || echo unknown)"
    echo "result=$result"
    echo "waited_sec=$waited"
    [[ -n "$ip" ]] && echo "wlan0_ipv4=$ip"
    echo "wlan0_operstate=$(cat /sys/class/net/wlan0/operstate 2>/dev/null || echo missing)"
    echo "default_route_line=${def_line:-"(none)"}"
    echo "default_via=${def_via:-"(none)"}"
    echo "default_dev=${def_dev:-"(none)"}"
    echo "dns_resolv=$(grep -E '^nameserver' /etc/resolv.conf 2>/dev/null | tr '\n' ' ' || echo "(none)")"
    echo "--- ip -br a ---"
    ip -br a || true
    echo "--- ip -4 addr ---"
    ip -4 addr || true
    echo "--- ip -4 route ---"
    ip -4 route || true
    echo "--- ip -4 route show default ---"
    ip -4 route show default || echo "(no default route)"
    echo "--- iw dev wlan0 link ---"
    iw dev wlan0 link 2>/dev/null || echo "(iw not available or no link)"
    echo "--- iw dev wlan0 info ---"
    iw dev wlan0 info 2>/dev/null || true
    echo "--- MAC ---"
    cat /sys/class/net/wlan0/address 2>/dev/null || true
    echo "--- resolv.conf ---"
    cat /etc/resolv.conf 2>/dev/null || true
    if [[ "$result" != "ok" ]]; then
      echo "HINT: check Imager SSID/PSK vs live AP; cloud-init wifi may still be settling"
    fi
  } >"$status"
}

# Wait for wlan0 IPv4; mirror status onto boot FAT for Windows card-read.
wait_for_wlan() {
  local boot_dir="$1"
  local max_sec="${2:-180}"
  local status="$boot_dir/bhvr-net-status.txt"
  local t=0
  local ip=""
  echo "waiting up to ${max_sec}s for wlan0 IPv4..."
  {
    echo "bhvr-net-status $(date -u -Iseconds)"
    echo "waiting_up_to_sec=$max_sec"
  } >"$status"
  while (( t < max_sec )); do
    ip="$(ip -4 -o addr show wlan0 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1 || true)"
    if [[ -n "$ip" ]]; then
      echo "wlan0 UP with IPv4=$ip after ${t}s"
      write_net_report "$status" "ok" "$t" "$ip"
      return 0
    fi
    if (( t % 30 == 0 )); then
      echo "  t=${t}s wlan0 still no IPv4; state=$(cat /sys/class/net/wlan0/operstate 2>/dev/null || echo missing)"
      ip -br a || true
      ip -4 route show default || true
    fi
    sleep 5
    t=$((t + 5))
  done
  echo "WARN: wlan0 has no IPv4 after ${max_sec}s"
  write_net_report "$status" "no_ipv4" "$max_sec" ""
  return 1
}

BOOT=""
for d in /boot/firmware /boot; do
  if [[ -d "$d/bhvr-cam/firstboot" ]]; then
    BOOT="$d"
    break
  fi
done
if [[ -z "$BOOT" ]]; then
  echo "ERROR: bhvr-cam payload not found under /boot/firmware or /boot"
  cleanup_cmdline || true
  exit 1
fi

echo "using payload at $BOOT/bhvr-cam"
rm -rf /var/lib/bhvr-src
mkdir -p /var/lib/bhvr-src
cp -a "$BOOT/bhvr-cam" /var/lib/bhvr-src/
find /var/lib/bhvr-src/bhvr-cam -type f \( -name '*.sh' -o -name '*.py' -o -name '*.service' -o -name '*.timer' \) \
  -exec sed -i 's/\r$//' {} +

rc=0
bash /var/lib/bhvr-src/bhvr-cam/firstboot/99-bhvr-cam.sh || rc=$?
echo "99-bhvr-cam.sh exit=$rc"

wifi_rc=0
wait_for_wlan "$BOOT" 180 || wifi_rc=$?
echo "wait_for_wlan exit=$wifi_rc"

# Units started before WiFi; bounce listen so journal is clear after assoc.
if [[ "$wifi_rc" -eq 0 ]]; then
  systemctl restart bhvr-cam-broker-listen.service 2>/dev/null || true
  systemctl start bhvr-cam-announce.service 2>/dev/null || true
fi

cleanup_cmdline || true
touch "$BOOT/bhvr-firstrun.done"
echo "bhvr-firstrun done $(date -u -Iseconds) rc=$rc wifi_rc=$wifi_rc"
# reboot handled by systemd.run_success_action=reboot on success path
# Prefer exit 0 so reboot happens even if WiFi was slow; status file has the truth.
exit 0
