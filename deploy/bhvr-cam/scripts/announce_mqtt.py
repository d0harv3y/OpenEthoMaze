#!/usr/bin/env python3
"""Announce this cam on MQTT (stdlib only — no mosquitto_clients).

Broker from /var/lib/bhvr/broker.env (UDP Invite) or MQTT_BROKER in env.
Backhaul: USB gadget preferred when carrier is real; WiFi fallback with
asymmetric hysteresis. See deploy/NETWORK.md (wired-primary overnight).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

CACHE = Path("/var/lib/bhvr/broker.env")


def _link_state_path() -> Path:
    """Root timer uses /var/lib/bhvr; manual admin runs fall back to cache dir."""
    preferred = Path("/var/lib/bhvr/link_state.json")
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        if os.access(preferred.parent, os.W_OK):
            return preferred
    except OSError:
        pass
    fallback = Path.home() / ".cache" / "bhvr" / "link_state.json"
    fallback.parent.mkdir(parents=True, exist_ok=True)
    return fallback

# Asymmetric hysteresis (grill Q7): leave USB → WiFi; fast return on plug.
# Default leave shortened to 10s after intentional-unplug testing (was 30).
USB_DOWN_BEFORE_WIFI_S = float(os.environ.get("BHVR_USB_DOWN_BEFORE_WIFI_S", "10"))
USB_UP_BEFORE_USB_S = float(os.environ.get("BHVR_USB_UP_BEFORE_USB_S", "5"))


def _looks_like_ipv4(token: str) -> bool:
    parts = token.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def _gateway_on_dev(dev: str) -> str | None:
    """IPv4 gateway learned via DHCP on ``dev`` (e.g. usb0 → NVR 192.168.7.1).

    systemd-networkd DHCPServer often installs a *host* route without ``via``::

        192.168.7.1 proto dhcp scope link src 192.168.7.41 metric 100

    Older parsers that only accepted ``default via …`` treated USB as down and
    left WiFi-less cams silent after NVR reboot (Invite cannot help them).
    """
    try:
        out = subprocess.check_output(
            ["ip", "-4", "route", "show", "dev", dev],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    host_route: str | None = None
    for line in out.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "default" and "via" in parts:
            return parts[parts.index("via") + 1]
        # Host route to DHCP router (no prefix length, not a subnet route).
        if (
            host_route is None
            and _looks_like_ipv4(parts[0])
            and "/" not in parts[0]
            and "via" not in parts
        ):
            host_route = parts[0]
    return host_route


def _carrier_up(dev: str) -> bool:
    """True when iface reports carrier (may stay 1 on gadget after host unplug)."""
    carrier = Path(f"/sys/class/net/{dev}/carrier")
    try:
        if carrier.is_file():
            return carrier.read_text(encoding="utf-8").strip() == "1"
    except OSError:
        return False
    # No carrier sysfs: fall back to operstate.
    oper = Path(f"/sys/class/net/{dev}/operstate")
    try:
        return oper.is_file() and oper.read_text(encoding="utf-8").strip() == "up"
    except OSError:
        return False


def _tcp_reachable(
    host: str,
    port: int,
    timeout_s: float = 0.8,
    *,
    source_ip: str | None = None,
) -> bool:
    """L3/L4 litmus — gadget often keeps carrier=1 after the NVR side is gone.

    Optional ``source_ip`` binds the client socket so dual-homed cams don't
    blackhole via a stale usb0 default route.
    """
    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_s)
        if source_ip:
            sock.bind((source_ip, 0))
        sock.connect((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def _usb_link_usable(usb_ip: str | None, usb_gw: str | None, *, mqtt_port: int) -> bool:
    """USB backhaul is OK only if carrier+addr+NVR gateway answers (MQTT)."""
    if not usb_ip or not usb_gw:
        return False
    if not _carrier_up("usb0"):
        return False
    # Bind to usb0 address so the probe cannot sneak out wlan0.
    return _tcp_reachable(usb_gw, mqtt_port, timeout_s=0.8, source_ip=usb_ip)


def _drop_stale_usb_routes(*, usb_ok: bool) -> None:
    """When tether is dead, drop usb0 default so WiFi MQTT/SSH is not blackholed."""
    if usb_ok:
        return
    try:
        out = subprocess.check_output(
            ["ip", "-4", "route", "show", "dev", "usb0"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return
    for line in out.splitlines():
        parts = line.split()
        if not parts or parts[0] != "default":
            continue
        # `ip route del` the exact default line on usb0 (best-effort, no sudo if root timer).
        cmd = ["ip", "route", "del", *parts]
        try:
            subprocess.run(cmd, check=False, capture_output=True, timeout=2)
            print(f"route: dropped stale {' '.join(parts)}", flush=True)
        except (OSError, subprocess.TimeoutExpired):
            pass


def _ipv4_on_dev(dev: str) -> str | None:
    try:
        out = subprocess.check_output(
            ["ip", "-4", "-o", "addr", "show", "dev", dev],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4 and "/" in parts[3]:
            return parts[3].split("/", 1)[0]
    return None


def _read_broker_cache() -> dict[str, str]:
    data: dict[str, str] = {}
    if not CACHE.is_file():
        return data
    try:
        text = CACHE.read_text(encoding="utf-8")
    except OSError:
        return data
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def _write_broker_cache(
    host: str,
    port: int,
    *,
    wifi_fallback: str | None = None,
) -> None:
    """Write active broker; keep MQTT_BROKER_WIFI for unplug failover."""
    cached = _read_broker_cache()
    wifi = wifi_fallback or cached.get("MQTT_BROKER_WIFI", "")
    # If we're pinning USB but current/primary was IoT, remember it.
    if _is_usb_subnet(host):
        prev = cached.get("MQTT_BROKER", "")
        if prev and not _is_usb_subnet(prev):
            wifi = prev
    elif not _is_usb_subnet(host):
        wifi = host
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"MQTT_BROKER={host}", f"MQTT_PORT={port}"]
        if wifi and not _is_usb_subnet(wifi):
            lines.append(f"MQTT_BROKER_WIFI={wifi}")
        CACHE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"warn: broker.env write failed: {exc}", flush=True)


def _is_usb_subnet(ip: str) -> bool:
    return (ip or "").startswith("192.168.7.")


def _sync_broker_for_link(
    *,
    usb_ok: bool,
    usb_gw: str | None,
    port: int,
) -> None:
    """Grill Q9: USB gateway when carrier up; on unplug restore WiFi Invite broker."""
    cached = _read_broker_cache()
    if usb_ok and usb_gw:
        if cached.get("MQTT_BROKER") != usb_gw:
            _write_broker_cache(usb_gw, port)
        return
    # USB down: never leave cams with only a dead 192.168.7.1 (that stalls announce → STALE).
    broker = cached.get("MQTT_BROKER", "")
    wifi = cached.get("MQTT_BROKER_WIFI", "")
    if broker and _is_usb_subnet(broker):
        if wifi and not _is_usb_subnet(wifi):
            _write_broker_cache(wifi, port, wifi_fallback=wifi)
            print(f"broker.env → WiFi fallback {wifi} (USB down)", flush=True)
        else:
            # Last resort: delete tether-only cache so Invite / env can supply a host.
            try:
                CACHE.unlink(missing_ok=True)
                print(
                    "broker.env cleared (USB down; no MQTT_BROKER_WIFI — hit Invite)",
                    flush=True,
                )
            except OSError:
                pass


def _broker_candidates(
    *,
    usb_ok: bool,
    usb_gw: str | None,
    usb_ip: str | None,
    wifi_ip: str | None,
    port: int,
) -> list[tuple[str, int, str | None]]:
    """Ordered (host, port, source_ip) for MQTT publish after unplug/plug.

    Prefer the active backhaul's broker and bind to that iface's address so a
    zombie usb0 default route cannot blackhole WiFi publishes (litmus cam3).
    """
    cached = _read_broker_cache()
    env_broker = (os.environ.get("MQTT_BROKER") or "").strip()
    broker = env_broker or cached.get("MQTT_BROKER", "")
    wifi = cached.get("MQTT_BROKER_WIFI", "")
    if wifi and _is_usb_subnet(wifi):
        wifi = ""
    # Env MQTT_BROKER on USB subnet is ignored when tether is dead (same as cache).
    if broker and _is_usb_subnet(broker) and not usb_ok:
        broker = ""

    out: list[tuple[str, int, str | None]] = []
    seen: set[str] = set()

    def add(host: str, src: str | None) -> None:
        host = (host or "").strip()
        if not host or host in seen:
            return
        seen.add(host)
        out.append((host, port, src))

    if usb_ok and usb_gw:
        add(usb_gw, usb_ip)
        if broker and not _is_usb_subnet(broker):
            add(broker, wifi_ip)
        if wifi:
            add(wifi, wifi_ip)
        return out

    # USB down: WiFi broker first, bind wlan0.
    if wifi:
        add(wifi, wifi_ip)
    if broker and not _is_usb_subnet(broker):
        add(broker, wifi_ip)
    if env_broker and not _is_usb_subnet(env_broker):
        add(env_broker, wifi_ip)
    return out


def _load_broker(
    *,
    usb_ok: bool = False,
    usb_gw: str | None = None,
    usb_ip: str | None = None,
    wifi_ip: str | None = None,
) -> tuple[str, int]:
    """Primary broker for logging; publish uses ``_broker_candidates``."""
    port = int(os.environ.get("MQTT_PORT", "1883"))
    cands = _broker_candidates(
        usb_ok=usb_ok, usb_gw=usb_gw, usb_ip=usb_ip, wifi_ip=wifi_ip, port=port
    )
    if cands:
        return cands[0][0], cands[0][1]
    raise SystemExit(
        "no broker — Invite cameras (UDP) or plug USB gadget (DHCP router on usb0)"
    )


def _load_link_state() -> dict[str, Any]:
    path = _link_state_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_link_state(state: dict[str, Any]) -> None:
    path = _link_state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    except OSError as exc:
        print(f"warn: link_state write failed: {exc}", flush=True)


def choose_backhaul(
    *,
    usb_ip: str | None,
    wifi_ip: str | None,
    usb_carrier: bool,
    prefer: str,
    now: float,
    state: dict[str, Any],
    usb_down_s: float = USB_DOWN_BEFORE_WIFI_S,
    usb_up_s: float = USB_UP_BEFORE_USB_S,
) -> tuple[str, str, dict[str, Any]]:
    """Return (active_ip, link, new_state).

    ``prefer``: auto | usb | wlan (NET_PREFER).
    """
    prefer = (prefer or "auto").strip().lower()
    if prefer in ("wifi", "wireless"):
        prefer = "wlan"
    usb_ok = bool(usb_carrier and usb_ip)
    wifi_ok = bool(wifi_ip)

    if prefer == "usb":
        if usb_ok:
            return usb_ip, "usb", {"link": "usb", "since": now, "usb_down_since": None}  # type: ignore[return-value]
        if wifi_ok:
            return wifi_ip, "wifi", {"link": "wifi", "since": now, "usb_down_since": None}  # type: ignore[return-value]
        raise SystemExit("no IPv4 address (NET_PREFER=usb)")

    if prefer == "wlan":
        if wifi_ok:
            return wifi_ip, "wifi", {"link": "wifi", "since": now, "usb_down_since": None}  # type: ignore[return-value]
        if usb_ok:
            return usb_ip, "usb", {"link": "usb", "since": now, "usb_down_since": None}  # type: ignore[return-value]
        raise SystemExit("no IPv4 address (NET_PREFER=wlan)")

    # auto + asymmetric hysteresis
    prev = str(state.get("link") or "")
    usb_down_since = state.get("usb_down_since")
    usb_up_since = state.get("usb_up_since")

    if usb_ok:
        usb_down_since = None
        if prev != "usb":
            if usb_up_since is None:
                usb_up_since = now
            if (now - float(usb_up_since)) >= usb_up_s or prev == "":
                return (
                    usb_ip,  # type: ignore[return-value]
                    "usb",
                    {"link": "usb", "since": now, "usb_down_since": None, "usb_up_since": None},
                )
            # Still in WiFi grace while USB just came back
            if wifi_ok and prev == "wifi":
                return (
                    wifi_ip,  # type: ignore[return-value]
                    "wifi",
                    {
                        "link": "wifi",
                        "since": state.get("since", now),
                        "usb_down_since": None,
                        "usb_up_since": usb_up_since,
                    },
                )
        return (
            usb_ip,  # type: ignore[return-value]
            "usb",
            {"link": "usb", "since": state.get("since", now), "usb_down_since": None, "usb_up_since": None},
        )

    # USB not OK (caller already treated zombie carrier / dead gateway as down).
    # No USB-IP hold here: gadget keeps carrier=1 after unplug, so a timed hold
    # just freezes ONLINE·USB while MQTT to 192.168.7.1 fails. Flip to WiFi ASAP.
    usb_up_since = None
    if prev == "usb" or prev == "":
        if usb_down_since is None:
            usb_down_since = now
        if wifi_ok:
            return (
                wifi_ip,  # type: ignore[return-value]
                "wifi",
                {
                    "link": "wifi",
                    "since": now,
                    "usb_down_since": usb_down_since,
                    "usb_up_since": None,
                    "last_usb_ip": state.get("last_usb_ip"),
                },
            )
    if wifi_ok:
        return (
            wifi_ip,  # type: ignore[return-value]
            "wifi",
            {
                "link": "wifi",
                "since": state.get("since", now),
                "usb_down_since": usb_down_since,
                "usb_up_since": None,
                "last_usb_ip": state.get("last_usb_ip"),
            },
        )
    raise SystemExit("no IPv4 address")


def _collect_ips(*, mqtt_port: int = 1883) -> tuple[str | None, str | None, bool, str | None]:
    usb_ip = _ipv4_on_dev("usb0")
    wifi_ip = _ipv4_on_dev("wlan0")
    usb_gw = _gateway_on_dev("usb0") if _carrier_up("usb0") else None
    # Treat gadget zombie (carrier up, host gone) as USB down.
    usb_ok = _usb_link_usable(usb_ip, usb_gw, mqtt_port=mqtt_port)
    return usb_ip, wifi_ip, usb_ok, usb_gw


def _read_env_sample() -> dict | None:
    """HTU21D sample from sibling htu21d.py or /usr/local/lib/bhvr/htu21d.py."""
    candidates = [
        Path(__file__).resolve().parent / "htu21d.py",
        Path("/usr/local/lib/bhvr/htu21d.py"),
        Path("/usr/local/bin/htu21d.py"),
    ]
    for path in candidates:
        if not path.is_file():
            continue
        parent = str(path.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        try:
            from htu21d import window_stats  # type: ignore[import-not-found]

            return window_stats()
        except Exception:
            continue
    return None


def _mqtt_publish(
    host: str,
    port: int,
    topic: str,
    payload: bytes,
    retain: bool,
    *,
    source_ip: str | None = None,
    timeout_s: float = 2.0,
) -> None:
    """Minimal MQTT 3.1.1 CONNECT + PUBLISH QoS0 + DISCONNECT."""

    def enc_str(s: str) -> bytes:
        b = s.encode("utf-8")
        return len(b).to_bytes(2, "big") + b

    client_id = f"bhvr-{os.uname().nodename}"[:23]
    var = b"\x00\x04MQTT\x04\x02\x00\x3c" + enc_str(client_id)
    connect = bytes([0x10, len(var)]) + var
    flags = 0x30 | (0x01 if retain else 0x00)
    topic_b = enc_str(topic)
    rem = topic_b + payload
    if len(rem) < 128:
        publish = bytes([flags, len(rem)]) + rem
    else:
        publish = bytes([flags, (len(rem) % 128) | 0x80, len(rem) // 128]) + rem
    disconnect = b"\xe0\x00"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout_s)
        if source_ip:
            sock.bind((source_ip, 0))
        sock.connect((host, int(port)))
        sock.sendall(connect)
        sock.settimeout(min(5.0, timeout_s + 3.0))
        ack = sock.recv(4)
        if len(ack) < 4 or ack[0] != 0x20:
            raise OSError(f"MQTT CONNACK failed: {ack!r}")
        if ack[3] != 0:
            raise OSError(f"MQTT connect refused code={ack[3]}")
        sock.sendall(publish)
        sock.sendall(disconnect)
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _mqtt_publish_failover(
    candidates: list[tuple[str, int, str | None]],
    topic: str,
    payload: bytes,
    *,
    retain: bool = True,
) -> tuple[str, int]:
    """Try each broker quickly; raise SystemExit if all fail."""
    errors: list[str] = []
    for host, port, source_ip in candidates:
        try:
            _mqtt_publish(
                host, port, topic, payload, retain, source_ip=source_ip, timeout_s=2.0
            )
            return host, port
        except OSError as exc:
            src = f" src={source_ip}" if source_ip else ""
            errors.append(f"{host}:{port}{src}: {exc}")
            print(f"warn: MQTT publish failed {host}:{port}{src}: {exc}", flush=True)
    raise SystemExit("MQTT publish failed: " + " | ".join(errors) if errors else "no brokers")


def main() -> int:
    env_path = Path("/etc/bhvr-cam.env")
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

    port = int(os.environ.get("MQTT_PORT", "1883"))
    usb_ip, wifi_ip, usb_ok, usb_gw = _collect_ips(mqtt_port=port)
    _drop_stale_usb_routes(usb_ok=usb_ok)
    _sync_broker_for_link(usb_ok=usb_ok, usb_gw=usb_gw, port=port)

    cam_id = os.environ.get("CAM_ID") or os.uname().nodename
    prefix = os.environ.get("MQTT_TOPIC_PREFIX", "bhvr/cam")
    raw_profile = os.environ.get("PROFILE", "720p")
    _legacy = {"720p30": "720p", "720p20": "720p", "480p30": "480p"}
    profile = _legacy.get(raw_profile, raw_profile)
    prefer = os.environ.get("NET_PREFER", "auto")

    now = time.time()
    state = _load_link_state()
    # usb_carrier arg = "usable tether" (carrier alone lies after host unplug).
    ip, link, new_state = choose_backhaul(
        usb_ip=usb_ip,
        wifi_ip=wifi_ip,
        usb_carrier=usb_ok,
        prefer=prefer,
        now=now,
        state=state,
    )
    if usb_ip:
        new_state["last_usb_ip"] = usb_ip
    _save_link_state(new_state)

    ips: dict[str, str] = {}
    if usb_ip:
        ips["usb"] = usb_ip
    if wifi_ip:
        ips["wifi"] = wifi_ip

    body: dict = {
        "id": cam_id,
        "ip": ip,
        "link": link,
        "profile": profile,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if ips:
        body["ips"] = ips

    env = _read_env_sample()
    if env and "temp_c" in env:
        body["temp_c"] = env["temp_c"]
        if "rh_pct" in env:
            body["rh_pct"] = env["rh_pct"]
        if isinstance(env.get("env"), dict):
            body["env"] = env["env"]
    payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
    topic = f"{prefix}/{cam_id}/state"
    candidates = _broker_candidates(
        usb_ok=usb_ok, usb_gw=usb_gw, usb_ip=usb_ip, wifi_ip=wifi_ip, port=port
    )
    if not candidates:
        raise SystemExit(
            "no broker — Invite cameras (UDP) or plug USB gadget (DHCP router on usb0)"
        )
    host, used_port = _mqtt_publish_failover(candidates, topic, payload, retain=True)
    print(f"announced {topic} -> {host}:{used_port} {payload.decode()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
