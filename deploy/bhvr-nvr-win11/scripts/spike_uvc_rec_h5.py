#!/usr/bin/env python3
"""Record one UVC cam → MPEG-TS → pack into bhvr session H5 (Win11 spike)."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "bhvr-kiosk"
sys.path.insert(0, str(ROOT))

from app import h5_archive  # noqa: E402
from app.capture_port import RecordSink  # noqa: E402
from app.capture_uvc_dshow import LocalUvcDshow, filter_uvc_only  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-id", default="", help="stable usb:… id (default: first vid_1871)")
    ap.add_argument("--cam-id", default="desk0")
    ap.add_argument("--subject", default="spike")
    ap.add_argument("--tag", default="uvc")
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="session folder (default moseq-mountain/ses-…)",
    )
    ap.add_argument("--snapshot", action="store_true", help="write crude JPEG before REC")
    ap.add_argument("--vid", default="1871")
    args = ap.parse_args()

    cap = LocalUvcDshow()
    srcs = filter_uvc_only(cap.list_sources(), vid=args.vid or None)
    if not srcs:
        print("FAIL no UVC sources", file=sys.stderr)
        return 2
    sid = args.source_id.strip() or srcs[0].source_id
    match = next((s for s in srcs if s.source_id == sid), None)
    if match is None:
        print(f"FAIL unknown source_id {sid}", file=sys.stderr)
        return 2

    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = args.out or (
        Path(__file__).resolve().parents[1] / "scratch" / f"{args.tag}-{utc}"
    )
    folder.mkdir(parents=True, exist_ok=True)

    cap.open(sid, args.cam_id)
    if args.snapshot:
        jpeg = cap.snapshot_jpeg(args.cam_id)
        if jpeg:
            (folder / f"{args.cam_id}_preview.jpg").write_bytes(jpeg)
            print(f"OK snapshot {len(jpeg)} B")
        else:
            print("WARN snapshot failed (device busy or unsupported)")

    stem = f"{args.subject}__{args.tag}__{args.cam_id}__p000"
    ts_path = folder / f"{stem}.ts"
    pts_path = folder / f"{stem}.pts"
    sink = RecordSink(ts_path=ts_path, pts_path=pts_path)
    print(f"REC {args.cam_id} ← {sid} for {args.seconds}s")
    cap.start_record(args.cam_id, sink)
    time.sleep(args.seconds)
    cap.stop_record(args.cam_id)
    cap.close(args.cam_id)

    if not ts_path.is_file() or ts_path.stat().st_size < 1000:
        print(f"FAIL empty/missing ts {ts_path}", file=sys.stderr)
        return 1
    print(f"OK ts bytes={ts_path.stat().st_size}")

    h5_path = h5_archive.cam_h5_path(
        folder, args.subject, args.cam_id, recording_tag=args.tag
    )
    h5_archive.create_cam_h5(
        h5_path,
        attrs={
            "cam_id": args.cam_id,
            "subject_id": args.subject,
            "recording_tag": args.tag,
            "source_id": sid,
            "pack_source": "win11_uvc_spike",
        },
    )
    result = h5_archive.pack_part(
        h5_path,
        part=0,
        ts_path=ts_path,
        pts_path=pts_path if pts_path.is_file() else None,
        attrs={"roll_reason": "spike", "source_id": sid},
        delete_loose=True,
        folder=folder,
        cam_id=args.cam_id,
        subject_id=args.subject,
        pack_session_sidecars=False,
    )
    print("pack", result)
    print(f"H5 {h5_path}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
