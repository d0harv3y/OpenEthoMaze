"""Fit keypoint-MoSeq on one SuperAnimal OF H5 (CPU, own alphabet)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from of_rear_classifier.fit_sa_video_kpms import FitSaVideoConfig, fit_sa_video, stem_from_sa_h5


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--h5", type=Path, required=True, help="SA-TVM pose H5")
    p.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help="kpMS project root (default: <out-root>/<recording_id>)",
    )
    p.add_argument(
        "--out-root",
        type=Path,
        default=Path(r"D:\Open Field - kpms_sa_per_video"),
        help="used when --project-dir omitted",
    )
    p.add_argument("--model-name", type=str, default="model")
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--ar-iters", type=int, default=50)
    p.add_argument("--full-iters", type=int, default=50)
    p.add_argument("--kappa-ar", type=float, default=1e8)
    p.add_argument("--kappa-full", type=float, default=1e4)
    p.add_argument("--latent-dim", type=int, default=None)
    p.add_argument("--likelihood-min", type=float, default=0.3)
    p.add_argument("--save-every", type=int, default=25)
    p.add_argument("--plots", action="store_true", help="write progress plots (slower)")
    args = p.parse_args(argv)

    rid = stem_from_sa_h5(args.h5)
    project_dir = args.project_dir or (args.out_root / rid)
    cfg = FitSaVideoConfig(
        ar_iters=args.ar_iters,
        full_iters=args.full_iters,
        fps=args.fps,
        likelihood_min=args.likelihood_min,
        latent_dim=args.latent_dim,
        kappa_ar=args.kappa_ar,
        kappa_full=args.kappa_full,
        save_every_n_iters=args.save_every,
        generate_progress_plots=args.plots,
    )
    fit_sa_video(args.h5, project_dir, cfg=cfg, model_name=args.model_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
