#!/usr/bin/env python3
"""Broadcast this host's MQTT broker address so cams need no static IP.

Packet (UTF-8 text):
  BHVR_MQTT_BROKER <ip> <port>

Sends to limited broadcast 255.255.255.255 and each interface's directed
broadcast (e.g. 10.248.239.255 for a /20) — campus APs often drop one or the other.

Default UDP port: 45454
"""

from __future__ import annotations

import argparse
import re
import socket
import subprocess
import time


def ipv4_addrs() -> list[str]:
    out: list[str] = []
    hostname = socket.gethostname()
    try:
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in out:
                out.append(ip)
    except socket.gaierror:
        pass
    # Fallback: UDP connect trick for "primary" egress IP (works offline too)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("127.") and ip not in out:
            out.insert(0, ip)
    except OSError:
        pass
    return out


def directed_broadcasts() -> list[str]:
    """Parse `ip -4 addr` for brd= addresses (subnet-directed broadcasts)."""
    try:
        text = subprocess.check_output(["ip", "-4", "-o", "addr", "show"], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    found: list[str] = []
    for m in re.finditer(r"\bbrd\s+(\d+\.\d+\.\d+\.\d+)", text):
        brd = m.group(1)
        if brd not in ("0.0.0.0", "255.255.255.255") and brd not in found:
            found.append(brd)
    return found


def udp_destinations(udp_port: int) -> list[tuple[str, int]]:
    dests = [("255.255.255.255", udp_port)]
    for brd in directed_broadcasts():
        dests.append((brd, udp_port))
    return dests


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    ap.add_argument("--udp-port", type=int, default=45454, help="beacon UDP port")
    ap.add_argument("--interval", type=float, default=30.0, help="seconds between beacons")
    ap.add_argument(
        "--ip",
        action="append",
        default=[],
        help="advertise this IPv4 (repeatable). Default: auto-detect",
    )
    ap.add_argument("--once", action="store_true", help="send one round and exit")
    args = ap.parse_args()

    ips = list(args.ip) if args.ip else ipv4_addrs()
    if not ips:
        raise SystemExit("no IPv4 address to advertise")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    dests = udp_destinations(args.udp_port)
    while True:
        for ip in ips:
            msg = f"BHVR_MQTT_BROKER {ip} {args.port}\n".encode("utf-8")
            for dest in dests:
                sock.sendto(msg, dest)
                print(f"beacon -> {dest[0]}:{dest[1]}  broker={ip}:{args.port}", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
