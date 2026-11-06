#!/bin/bash
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
for IP in 192.168.7.41 192.168.7.27; do
  echo "=== $IP ==="
  ssh "${KEY[@]}" "admin@${IP}" 'python3 -' <<'PY'
import fcntl, os, time, sys
I2C_SLAVE=0x0703
POLY=0x13100
def crc8(data):
    rem=0
    for byte in data:
        rem ^= byte<<8
        for _ in range(8):
            rem = ((rem<<1)^POLY) if rem&0x8000 else (rem<<1)
            rem &= 0xFFFF
    return (rem>>8)&0xFF
print("groups", os.getgroups(), "uid", os.getuid())
path="/dev/i2c-1"
fd=os.open(path, os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, 0x40)
# soft reset
try:
    os.write(fd, bytes([0xFE])); time.sleep(0.02); print("soft_reset ok")
except OSError as e:
    print("soft_reset", e)
for name,cmd,hold in [("HOLD_T",0xE3,True),("HOLD_H",0xE5,True),("NOHOLD_T",0xF3,False),("NOHOLD_H",0xF5,False)]:
    try:
        os.write(fd, bytes([cmd]))
        time.sleep(0.08)
        raw=os.read(fd,3)
        val=((raw[0]<<8)|raw[1])&0xFFFC
        ok=crc8(raw[:2])==raw[2]
        if name.endswith("_T"):
            phys=-46.85+175.72*(val/65536.0)
            unit="C"
        else:
            phys=-6.0+125.0*(val/65536.0)
            unit="%RH"
        print(f"{name}: hex={raw.hex()} val={val} crc={ok} {phys:.2f}{unit}")
    except OSError as e:
        print(f"{name}: ERR {e}")
os.close(fd)
PY
done
echo DIAG_RAW_DONE
