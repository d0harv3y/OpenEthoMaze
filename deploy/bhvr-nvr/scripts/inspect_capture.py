#!/usr/bin/env python3
"""Inspect whether a 'video.mp4' from rpicam is a real MP4 or raw H.264."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path("/media/admin/random/bhvr-tests")
    print("=== tree ===")
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                print(f"  {p.relative_to(root)}  {p.stat().st_size} B")
            else:
                print(f"  {p.relative_to(root)}/")
    vid = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if vid is None:
        cands = sorted(root.glob("*/video.mp4"))
        if not cands:
            print("no video.mp4 found")
            return 1
        vid = cands[-1]
    print(f"=== inspect {vid} ===")
    data = vid.read_bytes()
    print(f"size={len(data)}")
    print(f"head16={data[:16].hex()}")
    print(f"ascii_head={data[:32]!r}")
    has_ftyp = data[4:8] == b"ftyp" or b"ftyp" in data[:64]
    print(f"has_ftyp={has_ftyp}")
    print(f"has_moov={b'moov' in data}")
    print(f"has_mdat={b'mdat' in data}")
    sc = data.count(b"\x00\x00\x00\x01") + data.count(b"\x00\x00\x01")
    print(f"annexb_start_codes={sc}")
    # Likely raw H.264 if no ftyp but many start codes
    if not has_ftyp and sc > 10:
        print("VERDICT: raw H.264 elementary stream mislabeled as .mp4 — VLC often fails")
        print("fix: ffmpeg -framerate 30 -i video.mp4 -c copy video_fixed.mp4")
        print("  or: rename to .h264 and open / remux")
    elif has_ftyp and not (b"moov" in data):
        print("VERDICT: fragmented/incomplete MP4 (no moov) — common if encode killed early")
    elif has_ftyp and b"moov" in data:
        print("VERDICT: looks like a real MP4 container")
    else:
        print("VERDICT: unknown / empty-ish")

    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=format_name,duration,size:stream=codec_name,width,height,nb_frames,r_frame_rate",
                "-of",
                "default=nw=1",
                str(vid),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        print("=== ffprobe ===")
        print(r.stdout or r.stderr or f"rc={r.returncode}")
    except FileNotFoundError:
        print("ffprobe not installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
