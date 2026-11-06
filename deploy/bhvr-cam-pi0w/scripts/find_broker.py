#!/usr/bin/env python3
"""Listen for BHVR_MQTT_BROKER UDP beacons; write /var/lib/bhvr/broker.env

No static NVR IP required. Optional MQTT_BROKER in /etc/bhvr-cam.env still wins.
"""

from __future__ import annotations

import argparse
import os
import socket
import time
from pathlib import Path

CACHE = Path("/var/lib/bhvr/broker.env")
MAGIC = b"BHVR_MQTT_BROKER "


def write_cache(ip: str, port: int, path: Path) -> None:
    """Invite beacon → active broker; remember IoT IP as MQTT_BROKER_WIFI for unplug."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"MQTT_BROKER={ip}", f"MQTT_PORT={port}"]
    # Non-USB beacons are the WiFi failover host after tether pin overwrites MQTT_BROKER.
    if not ip.startswith("192.168.7."):
        lines.append(f"MQTT_BROKER_WIFI={ip}")
    else:
        # Keep prior WiFi fallback if present
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("MQTT_BROKER_WIFI="):
                    lines.append(line.strip())
                    break
    text = "\n".join(lines) + "\n"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--udp-port", type=int, default=45454)
    ap.add_argument(
        "--timeout",
        type=float,
        default=75.0,
        help="seconds to wait (0 = forever; for cam listen daemon)",
    )
    ap.add_argument("--cache", type=Path, default=CACHE)
    ap.add_argument(
        "--once",
        action="store_true",
        help="exit after first beacon (default). With --timeout 0, keep listening.",
    )
    args = ap.parse_args()
    forever = args.timeout <= 0
    exit_after_first = args.once or not forever

    # Explicit override still supported
    if os.environ.get("MQTT_BROKER") and exit_after_first:
        print(f"MQTT_BROKER already set to {os.environ['MQTT_BROKER']}; skip listen", flush=True)
        return 0

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("", args.udp_port))
    sock.settimeout(1.0)

    deadline = None if forever else time.monotonic() + args.timeout
    mode = "forever" if forever else f"{args.timeout}s"
    print(f"listening for broker beacon on UDP :{args.udp_port} ({mode})", flush=True)
    while forever or time.monotonic() < deadline:
        try:
            data, addr = sock.recvfrom(1024)
        except socket.timeout:
            continue
        if not data.startswith(MAGIC):
            continue
        try:
            line = data.decode("utf-8").strip().split()
            ip = line[1]
            port = int(line[2])
        except (IndexError, ValueError):
            continue
        write_cache(ip, port, args.cache)
        print(f"broker from {addr[0]}: {ip}:{port} -> {args.cache}", flush=True)
        if exit_after_first:
            return 0

    if args.cache.is_file():
        print(f"no new beacon; keeping existing {args.cache}", flush=True)
        return 0
    print("no broker beacon received", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
