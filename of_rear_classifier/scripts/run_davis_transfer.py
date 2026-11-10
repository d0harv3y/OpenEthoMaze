"""Goal B: Sturman Jin/Furkan/Oliver MLP → Davis SA videos (+ HITL majority vote).

Predict-only cohort (no Davis labels required)::

    uv run --extra sleap python of_rear_classifier/scripts/run_davis_transfer.py --videos all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from of_rear_classifier.davis_transfer import discover_davis_video_ids, run_davis_transfer
from of_rear_classifier.sturman_loocv import EXPERIMENTERS


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--oft-root",
        type=Path,
        default=Path(r"C:\Users\admin\code\DLCAnalyzer\data\OFT"),
    )
    p.add_argument(
        "--sa-h5-dir",
        type=Path,
        default=Path(r"D:\Open Field Frailty\Open Field - superanimal"),
    )
    p.add_argument(
        "--kpms-root",
        type=Path,
        default=Path(r"D:\Open Field Frailty\Open Field - kpms_sa_per_video"),
    )
    p.add_argument(
        "--quad-csv",
        type=Path,
        default=Path(r"D:\DeepLabCut\of_frailty\floor_quads\floor_quads.csv"),
    )
    p.add_argument(
        "--videos",
        type=str,
        default="Test 10,Test 42",
        help='comma list, or "all" for every *superanimal*.h5 under --sa-h5-dir',
    )
    p.add_argument("--davis-scorer", type=str, default="DOH")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=_ROOT / "runs" / "davis_transfer",
    )
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--device", type=str, default=None)
    p.add_argument(
        "--experimenters",
        type=str,
        default=",".join(EXPERIMENTERS),
    )
    p.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="re-score videos even if pred_*.csv already exist",
    )
    p.add_argument(
        "--no-majority",
        action="store_true",
        help="do not write pred_<video>_majority.csv",
    )
    args = p.parse_args(argv)
    if args.videos.strip().lower() == "all":
        videos = discover_davis_video_ids(args.sa_h5_dir)
        print(f"discovered {len(videos)} Davis videos under {args.sa_h5_dir}", flush=True)
    else:
        videos = [s.strip() for s in args.videos.split(",") if s.strip()]
    exps = tuple(s.strip() for s in args.experimenters.split(",") if s.strip())
    run_davis_transfer(
        oft_root=args.oft_root,
        davis_videos=videos,
        sa_h5_dir=args.sa_h5_dir,
        kpms_root=args.kpms_root,
        quad_csv=args.quad_csv,
        davis_scorer=args.davis_scorer,
        out_dir=args.out_dir,
        experimenters=exps,
        epochs=args.epochs,
        batch_size=args.batch_size,
        device=args.device,
        skip_existing=not args.no_skip_existing,
        write_majority=not args.no_majority,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
