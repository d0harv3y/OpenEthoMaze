#!/usr/bin/env python3
"""List DirectShow UVC sources with stable source_id (Win11 spike)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "bhvr-kiosk"
sys.path.insert(0, str(ROOT))

from app.capture_uvc_dshow import filter_uvc_only, list_dshow_video_sources  # noqa: E402


def main() -> int:
    srcs = list_dshow_video_sources()
    stick = filter_uvc_only(srcs, vid="1871")
    print(f"all_usb_video={len(srcs)} vid_1871={len(stick)}")
    for s in srcs:
        mark = " *" if "vid_1871" in s.source_id else ""
        print(f"{s.source_id}\t{s.label}{mark}")
        print(f"  alt={s.meta.get('dshow_alt', '')[:80]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
