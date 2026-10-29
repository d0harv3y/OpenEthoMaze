"""Host order / mismatch timeouts for USB↔WiFi LIVE path."""

from __future__ import annotations

from app.main import (
    _host_mismatches_link,
    _roster_hosts_for_cam,
    ssh_connect_timeout_for_host,
)


def test_wifi_link_tries_wifi_before_usb(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.online_cameras",
        lambda _cfg: [
            {
                "id": "bhvr-cam3",
                "ip": "10.248.235.74",
                "link": "wifi",
                "ips": {"usb": "192.168.7.28", "wifi": "10.248.235.74"},
            }
        ],
    )
    hosts = _roster_hosts_for_cam({}, "bhvr-cam3")
    assert hosts[0] == "10.248.235.74"
    assert hosts.index("10.248.235.74") < hosts.index("192.168.7.28")


def test_usb_link_tries_usb_before_wifi(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.online_cameras",
        lambda _cfg: [
            {
                "id": "bhvr-cam3",
                "ip": "192.168.7.28",
                "link": "usb",
                "ips": {"usb": "192.168.7.28", "wifi": "10.248.235.74"},
            }
        ],
    )
    hosts = _roster_hosts_for_cam({}, "bhvr-cam3")
    assert hosts[0] == "192.168.7.28"
    assert hosts.index("192.168.7.28") < hosts.index("10.248.235.74")


def test_mismatch_timeout_is_short() -> None:
    assert ssh_connect_timeout_for_host("192.168.7.28", mismatch=True) == 3
    assert ssh_connect_timeout_for_host("10.1.2.3", mismatch=False) == 30
    assert _host_mismatches_link("192.168.7.28", "wifi") is True
    assert _host_mismatches_link("10.1.2.3", "wifi") is False
