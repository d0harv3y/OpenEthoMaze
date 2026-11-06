#!/bin/bash
set -euo pipefail
grep -n 'fps: 3[05]\|fps: 15' /home/admin/bhvr-kiosk/app/templates/index.html || true
python3 <<'PY'
import concurrent.futures
import subprocess

def ping(ip: str) -> None:
    subprocess.run(
        ["ping", "-c", "1", "-W", "1", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

ips = (
    [f"10.248.232.{h}" for h in range(1, 255)]
    + [f"10.248.233.{h}" for h in range(1, 255)]
    + [f"10.248.234.{h}" for h in range(1, 255)]
)
print(f"ping {len(ips)}", flush=True)
with concurrent.futures.ThreadPoolExecutor(160) as ex:
    list(ex.map(ping, ips))
neigh = subprocess.check_output(["ip", "neigh"], text=True)
hits = [l for l in neigh.splitlines() if "b8:27:eb" in l.lower()]
print("--- Pi OUI ---", flush=True)
print("\n".join(hits) if hits else "(none)", flush=True)
print("--- lsusb gadget ---", flush=True)
subprocess.run(["lsusb"], check=False)
PY
