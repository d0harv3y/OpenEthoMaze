"""Parse helpers for dshow UVC ids (no hardware)."""

from __future__ import annotations

from app.capture_uvc_dshow import _dshow_pixel_format, _stable_id_from_alt


def test_stable_id_from_alt() -> None:
    alt = (
        r"@device_pnp_\\?\usb#vid_1871&pid_0306&mi_00#9&1b05c8cf&0&0000#"
        r"{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global"
    )
    sid = _stable_id_from_alt(alt)
    assert sid == "usb:vid_1871&pid_0306#9&1b05c8cf&0&0000"


def test_dshow_pixel_format_by_vid() -> None:
    assert _dshow_pixel_format("usb:vid_1871&pid_0306#x") == "yuyv422"
    assert _dshow_pixel_format("usb:vid_0ac8&pid_301b#8&6a25437&0&4") == "bgr24"
    assert _dshow_pixel_format("usb:vid_093a&pid_2468#8&6a25437&0&1") == "bgr24"
