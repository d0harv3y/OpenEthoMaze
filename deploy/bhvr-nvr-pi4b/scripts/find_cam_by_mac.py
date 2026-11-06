#!/usr/bin/env python3
"""Ping-sweep local /20 from NVR; find Raspberry Pi MAC in ARP neigh."""
from __future__ import annotations

import concurrent.futures
import re
import subprocess
import time

TARGET = "b8:27:eb:e1:a4:bb"
OUI = "b8:27:eb"


def ping(ip: str) -> tuple[str, bool]:
    r = subprocess.run(
        ["ping", "-c", "1", "-W", "1", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return ip, r.returncode == 0


def main() -> int:
    hosts = [
        f"10.248.{b}.{h}"
        for b in range(224, 240)
        for h in range(0, 256)
        if not (b == 224 and h == 0) and not (b == 239 and h == 255)
    ]
    print(f"probing {len(hosts)} hosts for {TARGET} (also any {OUI})", flush=True)
    t0 = time.time()
    alive: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=128) as ex:
        for ip, ok in ex.map(ping, hosts, chunksize=32):
            if ok:
                alive.append(ip)
    elapsed = time.time() - t0
    print(f"alive={len(alive)} in {elapsed:.1f}s", flush=True)

    neigh = subprocess.check_output(["ip", "neigh"], text=True)
    hits = [line for line in neigh.splitlines() if OUI in line.lower()]
    print("--- neigh hits (Pi OUI) ---", flush=True)
    print("\n".join(hits) if hits else "(none)", flush=True)
    exact = [line for line in hits if TARGET in line.lower()]
    print("--- exact MAC ---", flush=True)
    print("\n".join(exact) if exact else "(none)", flush=True)

    for line in hits:
        m = re.match(r"(\d+\.\d+\.\d+\.\d+)", line)
        if not m:
            continue
        ip = m.group(1)
        r = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=3",
                "-o",
                "StrictHostKeyChecking=no",
                f"admin@{ip}",
                "hostname",
            ],
            capture_output=True,
            text=True,
        )
        err = (r.stderr or "").strip().replace("\n", " ")[:100]
        print(f"ssh {ip}: rc={r.returncode} out={(r.stdout or '').strip()!r} err={err!r}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
