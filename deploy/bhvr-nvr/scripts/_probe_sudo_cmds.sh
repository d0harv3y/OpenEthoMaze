#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)
ip="${1:-192.168.7.31}"
ssh "${KEY[@]}" "admin@$ip" bash -s <<'REMOTE'
set +e
echo "hostname=$(hostname)"
echo "which mkdir=$(which mkdir); ls -la $(which mkdir)"
echo "which tee=$(which tee)"
for cmd in \
  "sudo -n /usr/bin/tee /dev/null </dev/null" \
  "sudo -n /usr/bin/mkdir -p /tmp/_bhvr_sudo_probe" \
  "sudo -n /bin/mkdir -p /tmp/_bhvr_sudo_probe2" \
  "sudo -n mkdir -p /tmp/_bhvr_sudo_probe3" \
  "sudo -n /usr/bin/chmod 755 /tmp/_bhvr_sudo_probe" \
  "sudo -n /usr/bin/systemctl is-active bhvr-cam-announce.timer" \
  "sudo -n true"
do
  echo "TRY: $cmd"
  eval "$cmd"; echo "  rc=$?"
done
# show sudoers drop-in if readable via sudo tee trick
sudo -n /usr/bin/tee /tmp/_bhvr_sudoers_dump </etc/sudoers.d/bhvr-cam >/dev/null 2>/tmp/_bhvr_sudoers_err \
  && echo "--- sudoers.d/bhvr-cam ---" && cat /tmp/_bhvr_sudoers_dump \
  || { echo "cannot dump sudoers"; cat /tmp/_bhvr_sudoers_err 2>/dev/null; }
REMOTE
