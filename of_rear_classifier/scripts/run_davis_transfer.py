"""Goal B: Sturman Jin/Furkan/Oliver MLP → Davis SA videos vs local scorer labels."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from of_rear_classifier.davis_transfer import run_davis_transfer
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
    p.add_argument("--videos", type=str, default="Test 10,Test 42")
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
    args = p.parse_args(argv)
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
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
