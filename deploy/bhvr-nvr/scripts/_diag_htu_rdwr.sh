#!/bin/bash
set -euxo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
scp "${KEY[@]}" /tmp/bhvr-htu/htu21d.py admin@192.168.7.27:/tmp/htu21d.py
scp "${KEY[@]}" /tmp/bhvr-htu/htu21d.py admin@192.168.7.41:/tmp/htu21d.py
for IP in 192.168.7.27 192.168.7.41; do
  echo "=== $IP ==="
  ssh "${KEY[@]}" "admin@${IP}" 'python3 /tmp/htu21d.py; python3 -' <<'PY'
import ctypes, fcntl, os, time
I2C_RDWR=0x0707
I2C_M_RD=0x0001
class Msg(ctypes.Structure):
    _fields_=[("addr",ctypes.c_uint16),("flags",ctypes.c_uint16),("len",ctypes.c_uint16),("buf",ctypes.POINTER(ctypes.c_uint8))]
class Data(ctypes.Structure):
    _fields_=[("msgs",ctypes.POINTER(Msg)),("nmsgs",ctypes.c_uint32)]
fd=os.open("/dev/i2c-1", os.O_RDWR)
addr=0x40
for name,cmd in [("T",0xE3),("H",0xE5)]:
    w=(ctypes.c_uint8*1)(cmd); r=(ctypes.c_uint8*3)()
    msgs=(Msg*2)(Msg(addr,0,1,w), Msg(addr,I2C_M_RD,3,r))
    try:
        fcntl.ioctl(fd, I2C_RDWR, Data(msgs,2))
        raw=bytes(r)
        print(name, raw.hex(), "status", raw[1]&3)
    except OSError as e:
        print(name, "ERR", e)
os.close(fd)
PY
done
echo RDWR_DONE
