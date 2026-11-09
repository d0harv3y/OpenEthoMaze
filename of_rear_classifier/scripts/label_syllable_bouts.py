"""Launch the OF rearing syllable labeler app (Goal B / multi-scorer).

PySide6 UI (``uv sync --extra gui``). With no args: file pickers + scorer
dialog. Per-scorer labels → ``model/labels/<scorer>.csv``.

Manual ``[`` / ``]`` frame ranges cover rearing split across two kpMS syllables.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from of_rear_classifier.labeler_app import run_app


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--video", type=Path, default=None)
    p.add_argument("--bouts", type=Path, default=None, help="syllable_bouts.csv")
    p.add_argument("--scorer", type=str, default=None, help="rater name / initials")
    p.add_argument("--fps", type=float, default=None)
    p.add_argument("--export-intervals", type=Path, default=None)
    p.add_argument("--video-id", type=str, default=None)
    p.add_argument(
        "--mlp-pred",
        type=Path,
        default=None,
        help="pred_<video>_<Experimenter>.csv (default: auto from runs/davis_transfer)",
    )
    p.add_argument("--no-auto-mlp", action="store_true", help="do not auto-load MLP pred CSV")
    args = p.parse_args(argv)
    return run_app(
        video=args.video,
        bouts=args.bouts,
        scorer=args.scorer,
        fps=args.fps,
        export_intervals=args.export_intervals,
        video_id=args.video_id,
        mlp_pred=args.mlp_pred,
        auto_load_mlp=not args.no_auto_mlp,
    )


if __name__ == "__main__":
    raise SystemExit(main())
