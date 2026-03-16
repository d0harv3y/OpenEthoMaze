#!/usr/bin/env python3
"""
Fix video files that report 0 frames with OpenCV (sleap_io default backend).

Some AVI files have metadata that OpenCV's VideoCapture cannot read (e.g. frame count),
while VLC and FFmpeg can. This script re-muxes such files with ffmpeg (stream copy, no
re-encode) so the fast OpenCV backend works for inference.

Usage:
  uv run python scripts/fix_zero_frame_videos.py path/to/video.avi
  uv run python scripts/fix_zero_frame_videos.py path/to/folder/
  uv run python scripts/fix_zero_frame_videos.py --replace path/to/video.avi

Requires: ffmpeg on PATH, sleap_io (with opencv backend).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def ffmpeg_available() -> bool:
    """Return True if ffmpeg is on PATH."""
    return shutil.which("ffmpeg") is not None


def get_frame_count_opencv(path: Path) -> int | None:
    """Return frame count using default (OpenCV) backend, or None on error."""
    try:
        import sleap_io as sio

        v = sio.load_video(str(path))
        v.open()
        n = len(v)
        v.close()
        return n
    except Exception:
        return None


def fix_video_ffmpeg(src: Path, dst: Path, verbose: bool = False) -> bool:
    """Re-mux video with ffmpeg -c copy. Returns True on success."""
    cmd = ["ffmpeg", "-y", "-i", str(src), "-c", "copy"]
    if dst.suffix.lower() == ".mp4":
        cmd += ["-movflags", "+faststart"]
    cmd.append(str(dst))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            if verbose:
                print(f"  Command: {' '.join(cmd)}", file=sys.stderr)
            err = (result.stderr or "").strip()
            if err:
                # FFmpeg prints version banner first; the real error is at the end
                tail = err[-1200:] if len(err) > 1200 else err
                print(f"  ffmpeg stderr (tail): {tail}", file=sys.stderr)
            return False
        return True
    except FileNotFoundError:
        print("  ffmpeg not found on PATH. Install ffmpeg and ensure it is in your PATH.", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fix videos that report 0 frames with OpenCV by re-muxing with ffmpeg."
    )
    ap.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Video file(s) or folder(s) to check and optionally fix.",
    )
    ap.add_argument(
        "--replace",
        action="store_true",
        help="Replace original file with fixed version (keeps a .bak backup).",
    )
    ap.add_argument(
        "--suffix",
        default=".fixed",
        help="Suffix for fixed files when not using --replace (default: .fixed).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list files that would be fixed, do not write.",
    )
    ap.add_argument(
        "--format",
        default="",
        help="Output format extension when not --replace (e.g. .mp4). Default: keep same as input.",
    )
    ap.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print ffmpeg command on failure.",
    )
    args = ap.parse_args()

    if not args.dry_run and not ffmpeg_available():
        print("ffmpeg not found on PATH. Install ffmpeg and ensure it is in your PATH.", file=sys.stderr)
        return 1

    # Collect all video files
    video_extensions = {".avi", ".mp4", ".mov", ".mkv", ".webm"}
    files: list[Path] = []
    for p in args.paths:
        if p.is_file():
            if p.suffix.lower() in video_extensions:
                files.append(p.resolve())
        elif p.is_dir():
            for ext in video_extensions:
                files.extend(p.resolve().rglob(f"*{ext}"))
        else:
            print(f"Warning: not found or not file/dir: {p}", file=sys.stderr)

    if not files:
        print("No video files found.", file=sys.stderr)
        return 1

    # Check which have 0 frames (OpenCV)
    zero_frame: list[Path] = []
    for f in files:
        n = get_frame_count_opencv(f)
        if n is not None and n == 0:
            zero_frame.append(f)

    if not zero_frame:
        print("No 0-frame videos found. All checked files report a positive frame count.")
        return 0

    print(f"Found {len(zero_frame)} file(s) that report 0 frames with OpenCV:")
    for f in zero_frame:
        print(f"  {f}")

    if args.dry_run:
        print("Dry run: not writing any files.")
        return 0

    # Fix each with ffmpeg
    out_ext = args.format if args.format.startswith(".") else args.format or None
    failed = []
    for src in zero_frame:
        if args.replace:
            # FFmpeg needs a standard extension; write to a temp file, then move over original.
            tmp = tempfile.NamedTemporaryFile(
                dir=src.parent, suffix=src.suffix, delete=False
            )
            tmp.close()
            dst = Path(tmp.name)
            backup = src.with_suffix(src.suffix + ".bak")
        else:
            stem = src.stem + args.suffix
            ext = out_ext or src.suffix
            dst = src.parent / (stem + ext)

        if not fix_video_ffmpeg(src, dst, verbose=args.verbose):
            print(f"  FAILED to create fixed file: {dst}", file=sys.stderr)
            if args.replace:
                dst.unlink(missing_ok=True)
            failed.append(src)
            continue

        n_after = get_frame_count_opencv(dst)
        if n_after is None or n_after == 0:
            print(f"  WARNING: fixed file still reports {n_after} frames: {dst}", file=sys.stderr)
            dst.unlink(missing_ok=True)
            failed.append(src)
            continue

        if args.replace:
            shutil.copy2(src, backup)
            shutil.move(str(dst), str(src))
            print(f"  Fixed: {src} ({n_after} frames) (backup: {backup})")
        else:
            print(f"  Fixed: {dst} ({n_after} frames)")

    if failed:
        print(f"Failed: {len(failed)} file(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
