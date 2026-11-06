#!/bin/bash
# Ping-sweep campus IoT /20 + NVR LAN for Pi OUI; try SSH hostname.
set -euo pipefail
python3 - <<'PY'
import concurrent.futures
import re
import subprocess

OUI = "b8:27:eb"
nets = [f"10.248.{b}.{h}" for b in range(224, 240) for h in range(1, 255)]
nets += [f"10.80.45.{h}" for h in range(1, 255)]


def ping(ip: str) -> str | None:
    r = subprocess.run(
        ["ping", "-c", "1", "-W", "1", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return ip if r.returncode == 0 else None


print(f"probing {len(nets)} hosts…", flush=True)
alive: list[str] = []
with concurrent.futures.ThreadPoolExecutor(max_workers=160) as ex:
    for ip in ex.map(ping, nets, chunksize=32):
        if ip:
            alive.append(ip)
print(f"alive={len(alive)}", flush=True)

neigh = subprocess.check_output(["ip", "neigh"], text=True)
hits = [l for l in neigh.splitlines() if OUI in l.lower()]
print("--- Pi OUI neigh ---", flush=True)
print("\n".join(hits) if hits else "(none)", flush=True)

cands: list[str] = []
for line in hits:
    m = re.match(r"(\d+\.\d+\.\d+\.\d+)", line)
    if m:
        cands.append(m.group(1))

key = "/home/admin/.ssh/id_ed25519_bhvr"
for ip in sorted(set(cands)):
    r = subprocess.run(
        [
            "ssh",
            "-i",
            key,
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=3",
            "-o",
            "StrictHostKeyChecking=accept-new",
            f"admin@{ip}",
            "hostname; cat /sys/class/net/wlan0/address 2>/dev/null; ip -4 -br a",
        ],
        capture_output=True,
        text=True,
    )
    out = (r.stdout or "").strip().replace("\n", " | ")
    err = (r.stderr or "").strip().replace("\n", " ")[:100]
    print(f"ssh {ip}: rc={r.returncode} out={out!r} err={err!r}", flush=True)

print("--- mqtt roster ---", flush=True)
subprocess.run(
    ["timeout", "3", "mosquitto_sub", "-h", "127.0.0.1", "-t", "bhvr/cam/+/state", "-v"],
    check=False,
)
PY
