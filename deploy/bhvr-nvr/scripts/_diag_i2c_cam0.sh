#!/bin/bash
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)
CAM_IP="${CAM_IP:-192.168.7.41}"
ssh "${KEY[@]}" "admin@${CAM_IP}" bash -s <<'REMOTE'
set -euxo pipefail
echo ===firmware===
grep -n i2c /boot/firmware/config.txt || true
echo ===boot===
grep -n i2c /boot/config.txt 2>/dev/null || true
echo ===tail_firmware===
tail -30 /boot/firmware/config.txt
echo ===sections===
grep -nE '^\[' /boot/firmware/config.txt || true
echo ===lsmod===
lsmod | grep -i i2c || true
echo ===modprobe===
sudo modprobe i2c-dev 2>&1 || true
sudo modprobe i2c_bcm2835 2>&1 || true
ls -la /dev/i2c-* 2>&1 || true
echo ===vcgencmd===
vcgencmd get_config i2c_arm 2>&1 || true
vcgencmd get_config int 2>&1 | grep -i i2c || true
echo ===raspi===
which raspi-config && sudo raspi-config nonint get_i2c 2>&1 || true
REMOTE
echo DIAG_DONE
