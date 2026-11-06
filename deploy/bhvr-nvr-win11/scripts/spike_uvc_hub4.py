#!/usr/bin/env python3
"""Litmus: N simultaneous UVC on one host (default 4 × vid_1871) → MPEG-TS files.

Reports per-cam bytes/s. Fail if any cam writes ~0 or ffmpeg dies early.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "bhvr-kiosk"
sys.path.insert(0, str(ROOT))

from app.capture_port import RecordSink  # noqa: E402
from app.capture_uvc_dshow import LocalUvcDshow, filter_uvc_only  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--n",
        type=int,
        default=3,
        help="how many cams (default 3 — accepted per-uplink ceiling)",
    )
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--vid", default="1871", help="USB VID filter (empty=all)")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "scratch" / "hub4",
    )
    ap.add_argument(
        "--width",
        type=int,
        default=320,
        help="default 320 (4×640 YUYV often exceeds USB2 hub bw)",
    )
    ap.add_argument("--height", type=int, default=240)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument(
        "--stagger-ms",
        type=int,
        default=400,
        help="delay between starting each recorder (dshow graph settle)",
    )
    args = ap.parse_args()

    cap = LocalUvcDshow(width=args.width, height=args.height, fps=args.fps)
    vid = (args.vid or "").strip() or None
    srcs = filter_uvc_only(cap.list_sources(), vid=vid)
    if len(srcs) < args.n:
        print(
            f"FAIL need {args.n} sources, found {len(srcs)} "
            f"(vid={vid or 'any'})",
            file=sys.stderr,
        )
        for s in srcs:
            print(f"  {s.source_id}  {s.label}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    # wipe prior run so FAIL≠stale empty
    for p in args.out.glob("uvc*"):
        p.unlink(missing_ok=True)
    chosen = srcs[: args.n]
    yuyv_mbs = (
        args.width * args.height * 2 * args.fps * args.n / (1024 * 1024)
    )
    print(
        f"recording n={args.n} {args.width}x{args.height}@{args.fps} "
        f"~{yuyv_mbs:.1f} MiB/s raw YUYV for {args.seconds}s → {args.out}"
    )
    for i, s in enumerate(chosen):
        cam = f"uvc{i}"
        print(f"  open {cam} ← {s.source_id}")
        cap.open(s.source_id, cam)
        sink = RecordSink(
            ts_path=args.out / f"{cam}.ts",
            pts_path=args.out / f"{cam}.pts",
        )
        cap.start_record(cam, sink)
        if args.stagger_ms > 0 and i + 1 < args.n:
            time.sleep(args.stagger_ms / 1000.0)

    t0 = time.monotonic()
    time.sleep(args.seconds)
    elapsed = time.monotonic() - t0

    ok = True
    for i in range(args.n):
        cam = f"uvc{i}"
        cap.stop_record(cam)
        cap.close(cam)
        ts = args.out / f"{cam}.ts"
        nbytes = ts.stat().st_size if ts.is_file() else 0
        rate = nbytes / max(elapsed, 1e-6)
        status = "OK" if nbytes > 50_000 else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"{status} {cam} bytes={nbytes} rate={rate / 1024:.1f} KiB/s")
        if status == "FAIL":
            pts = args.out / f"{cam}.pts"
            if pts.is_file():
                tail = pts.read_text(encoding="utf-8", errors="replace")[-400:]
                print(f"  pts/stderr tail:\n{tail}")

    print("PASS" if ok else "FAIL hub litmus")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
