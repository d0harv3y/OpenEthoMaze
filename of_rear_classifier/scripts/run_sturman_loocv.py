"""Goal A: Sturman OFT LOOCV (all annotators). Run from OpenEthoMaze repo root."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from of_rear_classifier.sturman_loocv import EXPERIMENTERS, run_sturman_loocv


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--oft-root",
        type=Path,
        default=Path(r"C:\Users\admin\code\DLCAnalyzer\data\OFT"),
        help="DLCAnalyzer data/OFT (Labels + Output_DLC)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=_ROOT / "runs" / "sturman_loocv",
        help="artifact folder (fold_metrics.csv, summary.json)",
    )
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=256, help="default 256 (Sturman used 32; larger is fine)")
    p.add_argument("--device", type=str, default=None, help="cuda|cpu (default: auto)")
    p.add_argument(
        "--experimenters",
        type=str,
        default=",".join(EXPERIMENTERS),
        help="comma list (default: Jin,Furkan,Oliver)",
    )
    args = p.parse_args(argv)
    exps = tuple(s.strip() for s in args.experimenters.split(",") if s.strip())
    run_sturman_loocv(
        oft_root=args.oft_root,
        out_dir=args.out_dir,
        experimenters=exps,
        epochs=args.epochs,
        batch_size=args.batch_size,
        device=args.device,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
