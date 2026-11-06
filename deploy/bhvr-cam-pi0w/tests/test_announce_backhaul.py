"""Unit tests for announce backhaul selection (no hardware)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "announce_mqtt.py"
_spec = importlib.util.spec_from_file_location("announce_mqtt", _SCRIPTS)
assert _spec and _spec.loader
announce_mqtt = importlib.util.module_from_spec(_spec)
sys.modules["announce_mqtt"] = announce_mqtt
_spec.loader.exec_module(announce_mqtt)

choose_backhaul = announce_mqtt.choose_backhaul


def test_unplug_flips_wifi_immediately() -> None:
    """Caller passes usb_carrier=False when gateway unreachable (zombie carrier)."""
    st: dict = {"link": "usb", "since": 1000.0, "last_usb_ip": "192.168.7.41"}
    ip, link, _ = choose_backhaul(
        usb_ip="192.168.7.41",
        wifi_ip="10.248.238.167",
        usb_carrier=False,
        prefer="auto",
        now=1010.0,
        state=st,
        usb_down_s=10,
        usb_up_s=5,
    )
    assert link == "wifi" and ip == "10.248.238.167"


def test_plug_returns_usb_after_short_grace() -> None:
    st = {"link": "wifi", "since": 2000.0}
    ip, link, st2 = choose_backhaul(
        usb_ip="192.168.7.41",
        wifi_ip="10.248.238.167",
        usb_carrier=True,
        prefer="auto",
        now=2001.0,
        state=st,
        usb_down_s=10,
        usb_up_s=5,
    )
    assert link == "wifi"
    ip, link, _ = choose_backhaul(
        usb_ip="192.168.7.41",
        wifi_ip="10.248.238.167",
        usb_carrier=True,
        prefer="auto",
        now=2007.0,
        state=st2,
        usb_down_s=10,
        usb_up_s=5,
    )
    assert link == "usb" and ip == "192.168.7.41"


def test_prefer_wlan_ignores_usb() -> None:
    ip, link, _ = choose_backhaul(
        usb_ip="192.168.7.41",
        wifi_ip="10.1.2.3",
        usb_carrier=True,
        prefer="wlan",
        now=1.0,
        state={},
    )
    assert link == "wifi" and ip == "10.1.2.3"


def test_zombie_usb_addr_without_carrier_uses_wifi() -> None:
    ip, link, _ = choose_backhaul(
        usb_ip="192.168.7.41",
        wifi_ip="10.1.2.3",
        usb_carrier=False,
        prefer="auto",
        now=100.0,
        state={"link": "wifi", "since": 50.0},
        usb_down_s=10,
        usb_up_s=5,
    )
    assert link == "wifi" and ip == "10.1.2.3"


def test_broker_candidates_usb_down_prefers_wifi_bound() -> None:
    """After unplug: WiFi broker first, source bind = wlan address."""
    announce_mqtt._read_broker_cache = lambda: {  # type: ignore[method-assign]
        "MQTT_BROKER": "192.168.7.1",
        "MQTT_BROKER_WIFI": "10.248.238.22",
        "MQTT_PORT": "1883",
    }
    cands = announce_mqtt._broker_candidates(
        usb_ok=False,
        usb_gw="192.168.7.1",
        usb_ip="192.168.7.28",
        wifi_ip="10.248.235.74",
        port=1883,
    )
    assert cands[0] == ("10.248.238.22", 1883, "10.248.235.74")
    assert all(not h.startswith("192.168.7.") for h, _, _ in cands)


def test_broker_candidates_usb_ok_binds_usb() -> None:
    announce_mqtt._read_broker_cache = lambda: {  # type: ignore[method-assign]
        "MQTT_BROKER": "192.168.7.1",
        "MQTT_BROKER_WIFI": "10.248.238.22",
    }
    cands = announce_mqtt._broker_candidates(
        usb_ok=True,
        usb_gw="192.168.7.1",
        usb_ip="192.168.7.28",
        wifi_ip="10.248.235.74",
        port=1883,
    )
    assert cands[0] == ("192.168.7.1", 1883, "192.168.7.28")


def test_gateway_on_dev_accepts_networkd_host_route(monkeypatch) -> None:
    """networkd DHCPServer: host route without ``via`` (post-reboot USB silent)."""
    sample = (
        "192.168.7.0/24 proto kernel scope link src 192.168.7.41 metric 100\n"
        "192.168.7.1 proto dhcp scope link src 192.168.7.41 metric 100\n"
    )

    def fake_check_output(cmd, text=True, stderr=None):  # noqa: ANN001
        assert "usb0" in cmd
        return sample

    monkeypatch.setattr(announce_mqtt.subprocess, "check_output", fake_check_output)
    assert announce_mqtt._gateway_on_dev("usb0") == "192.168.7.1"


def test_gateway_on_dev_prefers_default_via(monkeypatch) -> None:
    sample = (
        "default via 192.168.7.1 proto dhcp metric 100\n"
        "192.168.7.0/24 proto kernel scope link src 192.168.7.41\n"
    )

    def fake_check_output(cmd, text=True, stderr=None):  # noqa: ANN001
        return sample

    monkeypatch.setattr(announce_mqtt.subprocess, "check_output", fake_check_output)
    assert announce_mqtt._gateway_on_dev("usb0") == "192.168.7.1"
