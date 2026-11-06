#!/bin/bash
set +e
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
for ip in 192.168.7.31 192.168.7.28 192.168.7.27; do
  echo "######## $ip ########"
  ssh "${KEY[@]}" "admin@$ip" 'bash -s' <<'REMOTE'
set +e
hostname
echo "=== i2c ==="
ls -l /dev/i2c-1 2>&1
i2cdetect -y 1 2>/dev/null || sudo -n i2cdetect -y 1 2>/dev/null || echo no_i2cdetect
echo "=== htu files ==="
ls -la /usr/local/lib/bhvr/htu21d.py /usr/local/bin/htu21d.py /usr/local/bin/bhvr-cam-announce 2>&1
echo "=== sampler ==="
systemctl is-active bhvr-cam-htu-sample.timer bhvr-cam-htu-sample.service 2>&1
systemctl list-units 'bhvr*htu*' --all 2>&1 | head -10
ls /tmp/bhvr-htu* 2>/dev/null; ls /var/lib/bhvr/*htu* 2>/dev/null; ls /run/bhvr* 2>/dev/null
echo "=== window_stats ==="
python3 - <<'PY'
import sys
sys.path.insert(0, "/usr/local/lib/bhvr")
try:
    from htu21d import window_stats, sample_once
    print("window", window_stats())
    try:
        print("once", sample_once())
    except Exception as e:
        print("once_err", type(e).__name__, e)
except Exception as e:
    print("import_err", type(e).__name__, e)
PY
echo "=== announce env import path ==="
grep -n 'htu21d\|window_stats\|_read_env' /usr/local/bin/bhvr-cam-announce | head -15
python3 /usr/local/bin/bhvr-cam-announce 2>&1 | tail -3
REMOTE
done
