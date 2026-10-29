"""Roster IP → USB / WiFi badge mode."""

from app.main import announce_link_mode, ssh_connect_timeout_for_host


def test_announce_link_mode_usb_wifi_other() -> None:
    assert announce_link_mode("192.168.7.31") == "usb"
    assert announce_link_mode("10.248.229.141") == "wifi"
    assert announce_link_mode("172.16.0.5") == "other"
    assert announce_link_mode("") == "other"
    assert announce_link_mode("192.168.7.31", "wifi") == "wifi"
    assert announce_link_mode("10.1.2.3", "usb") == "usb"


def test_ssh_connect_timeout_wifi_longer() -> None:
    assert ssh_connect_timeout_for_host("192.168.7.41") == 15
    assert ssh_connect_timeout_for_host("10.248.238.167") == 30
