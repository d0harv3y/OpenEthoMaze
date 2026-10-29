#!/bin/bash
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
# Focus cam1 (outside case / room temp).
IP=192.168.7.27
ssh "${KEY[@]}" "admin@${IP}" 'python3 -' <<'PY'
import fcntl, os, time, struct
I2C_SLAVE=0x0703
I2C_RDWR=0x0707
POLY=0x13100

def crc8(data):
    rem=0
    for byte in data:
        rem ^= byte<<8
        for _ in range(8):
            rem = ((rem<<1)^POLY) if rem&0x8000 else (rem<<1)
            rem &= 0xFFFF
    return (rem>>8)&0xFF

fd=os.open("/dev/i2c-1", os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, 0x40)

def try_cmd(label, cmd, waits=(0.02,0.05,0.08,0.12,0.2)):
    for w in waits:
        try:
            os.write(fd, bytes([cmd]))
            time.sleep(w)
            raw=os.read(fd,3)
            val=((raw[0]<<8)|raw[1])&0xFFFC
            st=raw[1]&0x03
            print(f"{label} wait={w}: hex={raw.hex()} val={val} status={st} crc={crc8(raw[:2])==raw[2]}")
            return
        except OSError as e:
            print(f"{label} wait={w}: ERR {e}")
    print(f"{label}: all waits failed")

# User register (default often 0x02)
try:
    os.write(fd, bytes([0xE7]))
    time.sleep(0.01)
    ureg=os.read(fd,1)
    print("user_reg", ureg.hex() if ureg else None)
except OSError as e:
    print("user_reg ERR", e)

# Humidity-only first (fresh open already)
try_cmd("HUM_FIRST_F5", 0xF5)
try_cmd("HUM_FIRST_E5", 0xE5)

# Temp then hum with long gap
os.write(fd, bytes([0xF3])); time.sleep(0.1); t=os.read(fd,3)
print("temp", t.hex(), -46.85+175.72*((((t[0]<<8)|t[1])&0xFFFC)/65536))
try_cmd("HUM_AFTER_T_F5", 0xF5)
try_cmd("HUM_AFTER_T_E5", 0xE5)

# Soft reset then only humidity after 100ms
os.write(fd, bytes([0xFE])); time.sleep(0.1)
try_cmd("HUM_POST_RESET_F5", 0xF5)

# Scan common addrs briefly
for addr in (0x40, 0x41, 0x44, 0x45, 0x70):
    try:
        fcntl.ioctl(fd, I2C_SLAVE, addr)
        os.write(fd, bytes([0xE7]))
        time.sleep(0.005)
        b=os.read(fd,1)
        print(f"probe 0x{addr:02x} ureg={b.hex()}")
    except OSError as e:
        print(f"probe 0x{addr:02x} fail")

os.close(fd)
print("DEEP_DONE")
PY
echo DEEP_HOST_DONE
