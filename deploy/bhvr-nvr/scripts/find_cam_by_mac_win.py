#!/usr/bin/env python3
"""Ping-sweep 10.248.224.0/20 from a Windows laptop; find Pi MAC in arp -a.

Example (PowerShell):
  cd C:\\Users\\admin\\code\\OpenEthoMaze\\deploy\\bhvr-nvr\\scripts
  python .\\find_cam_by_mac_win.py
  python .\\find_cam_by_mac_win.py --mac b8-27-eb-e1-a4-bb
"""

from __future__ import annotations

import argparse
import concurrent.futures
import subprocess
import time


def norm_mac(s: str) -> str:
    return s.lower().replace(":", "-").replace(".", "-")


def ping(ip: str, timeout_ms: int) -> tuple[str, bool]:
    r = subprocess.run(
        ["ping", "-n", "1", "-w", str(timeout_ms), ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return ip, r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mac", default="b8-27-eb-e1-a4-bb", help="target MAC (any separator)")
    ap.add_argument("--workers", type=int, default=128)
    ap.add_argument("--timeout-ms", type=int, default=400)
    args = ap.parse_args()
    target = norm_mac(args.mac)
    oui = "-".join(target.split("-")[:3])

    hosts = [
        f"10.248.{b}.{h}"
        for b in range(224, 240)
        for h in range(256)
        if not (b == 224 and h == 0) and not (b == 239 and h == 255)
    ]
    print(f"probing {len(hosts)} hosts for {target} (OUI {oui})", flush=True)
    t0 = time.time()
    alive: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(ping, ip, args.timeout_ms) for ip in hosts]
        for fut in concurrent.futures.as_completed(futs):
            ip, ok = fut.result()
            if ok:
                alive.append(ip)
    print(f"alive={len(alive)} in {time.time() - t0:.1f}s", flush=True)

    arp = subprocess.check_output(["arp", "-a"], text=True, errors="replace")
    lines = arp.splitlines()
    hits = [ln for ln in lines if oui in norm_mac(ln)]
    exact = [ln for ln in lines if target in norm_mac(ln)]
    print("--- arp Pi OUI ---", flush=True)
    print("\n".join(hits) if hits else "(none)", flush=True)
    print("--- exact MAC ---", flush=True)
    print("\n".join(exact) if exact else "(none)", flush=True)
    if exact:
        # first IPv4 on the line
        for ln in exact:
            parts = ln.split()
            for p in parts:
                if p.count(".") == 3:
                    print(f"try: ssh admin@{p}", flush=True)
                    break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
