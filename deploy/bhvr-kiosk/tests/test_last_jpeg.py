"""_last_jpeg helper for UVC still warm-up."""

from __future__ import annotations

from app.capture_uvc_dshow import _last_jpeg


def test_last_jpeg_picks_trailing_frame() -> None:
    a = b"\xff\xd8" + b"AAA" + b"\xff\xd9"
    b = b"\xff\xd8" + b"BBB" + b"\xff\xd9"
    assert _last_jpeg(a + b) == b
    assert _last_jpeg(b"") is None
    assert _last_jpeg(b"\xff\xd8noend") is None
