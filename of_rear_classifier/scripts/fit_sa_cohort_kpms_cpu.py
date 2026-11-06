"""Fit keypoint-MoSeq per SuperAnimal OF video (CPU). No shared alphabet.

Each H5 → ``<out-root>/<recording_id>/model/{results.h5,syllable_bouts.csv}``.
Syllable ids are **local** to that video — for Goal B bout labeling, not
cross-session ethograms.

Mirror layout (this box vs other PC)::

    D:\\Open Field - superanimal\\*.h5   ↔   H:\\Open Field - superanimal\\*.h5
    D:\\Open Field - mp4\\Test N.mp4     ↔   H:\\Open Field - mp4\\Test N.mp4
    D:\\Open Field - kpms_sa_per_video  ↔   H:\\Open Field - kpms_sa_per_video
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from of_rear_classifier.fit_sa_video_kpms import FitSaVideoConfig, fit_sa_cohort


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--h5-dir",
        type=Path,
        required=True,
        help="folder of *_superanimal_*.h5 (D:\\… or H:\\…)",
    )
    p.add_argument(
        "--out-root",
        type=Path,
        required=True,
        help="per-video project parent (e.g. H:\\Open Field - kpms_sa_per_video)",
    )
    p.add_argument("--only", type=str, nargs="*", default=None, help='e.g. "Test 10" "Test 27"')
    p.add_argument("--glob", type=str, default="*superanimal*.h5")
    p.add_argument("--model-name", type=str, default="model")
    p.add_argument("--no-skip-existing", action="store_true")
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--ar-iters", type=int, default=50)
    p.add_argument("--full-iters", type=int, default=50)
    p.add_argument("--kappa-ar", type=float, default=1e8)
    p.add_argument("--kappa-full", type=float, default=1e4)
    p.add_argument("--latent-dim", type=int, default=None)
    p.add_argument("--likelihood-min", type=float, default=0.3)
    p.add_argument("--save-every", type=int, default=25)
    p.add_argument("--plots", action="store_true")
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        help="concurrent video fits (process pool). On 128 GB try 8–16 for ~20 min clips.",
    )
    args = p.parse_args(argv)

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
    rows = fit_sa_cohort(
        args.h5_dir,
        args.out_root,
        cfg=cfg,
        model_name=args.model_name,
        skip_existing=not args.no_skip_existing,
        only=args.only,
        glob_pat=args.glob,
        workers=args.workers,
    )
    n_ok = sum(1 for r in rows if "error" not in r)
    n_err = sum(1 for r in rows if "error" in r)
    print(f"done: {n_ok} ok/skip, {n_err} failed / {len(rows)} total", flush=True)
    return 1 if n_err else 0


if __name__ == "__main__":
    raise SystemExit(main())
