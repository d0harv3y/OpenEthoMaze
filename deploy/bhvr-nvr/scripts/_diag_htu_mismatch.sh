#!/bin/bash
# Was HTU working with an older announce API? Compare cam0 (works) vs cam2/3.
set +e
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10)
for spec in "cam0wifi:10.248.238.167" "cam2:192.168.7.31" "cam3:192.168.7.28"; do
  label=${spec%%:*}; host=${spec##*:}
  echo "######## $label $host ########"
  ssh "${KEY[@]}" "admin@$host" 'bash -s' <<'REMOTE'
set +e
hostname
echo "htu21d bytes/mtime:"; ls -la /usr/local/lib/bhvr/htu21d.py 2>&1
echo "defs:"; grep -E '^def ' /usr/local/lib/bhvr/htu21d.py 2>/dev/null
echo "announce mtime:"; ls -la /usr/local/bin/bhvr-cam-announce
echo "announce imports:"; grep -n 'from htu21d import\|read_htu\|window_stats\|smoothed' /usr/local/bin/bhvr-cam-announce | head -10
echo "sampler:"; systemctl is-active bhvr-cam-htu-sample.timer 2>&1; ls /etc/systemd/system/bhvr-cam-htu-sample.* 2>&1
REMOTE
done
