"""
Build a fixed kpMS exemplar trajectory HDF5 from **training** ``results.h5``.

Uses ``selected_trials.csv`` from the same fit run and ``build_kpms_inputs`` (not apply-stage
filtering). For **native** kpMS ``results.h5`` where syllables span every video frame, pass
``--retain-all-sleap-frames`` so coordinate length matches ``results`` (ORM fit defaults omit
dropped frames and stay aligned with ORM-trained models only).

Example (NOR native param-scan)::

    uv run python scripts/build_kpms_training_exemplar_table.py ^
      --model-dir "D:/work sack/impress data/NOR video/moseq_project/moseq_251017/paramscan_s1-1e6_s2-1e4_ss-50" ^
      --retain-all-sleap-frames

Writes ``training_exemplar_table.h5`` in ``--model-dir`` by default. Use it with::

    uv run python scripts/render_trial_overlay.py ... ^
      --kpms-h5 path/to/results_apply.h5 ^
      --kpms-training-exemplars path/to/training_exemplar_table.h5
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.kpms.training_exemplar_table import (
    TrainingExemplarBuildParams,
    compute_training_typical_trajectories,
    load_selected_trials_manifests,
    save_training_exemplar_table,
)


def _pre_cfg_from_fit_summary(model_dir: Path) -> KpmsPreprocessConfig | None:
    p = model_dir / "fit_summary.json"
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    raw = data.get("preprocess_config")
    if not isinstance(raw, dict):
        return None
    try:
        return KpmsPreprocessConfig(
            min_fragment_frames=int(raw.get("min_fragment_frames", 4)),
            jump_filter_cm=float(raw.get("jump_filter_cm", 15.0)),
            jump_filter_lookahead_frames=int(raw.get("jump_filter_lookahead_frames", 3)),
            px_per_cm=float(raw.get("px_per_cm", 2.42)),
            retain_all_frames=bool(raw.get("retain_all_frames", False)),
        )
    except (TypeError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build training-derived kpMS exemplar table HDF5 for unified overlay tray."
    )
    ap.add_argument(
        "--model-dir",
        type=Path,
        required=True,
        help="kpMS model directory (contains selected_trials.csv and training results.h5)",
    )
    ap.add_argument(
        "--results-h5",
        type=Path,
        default=None,
        help="Training results (default: <model-dir>/results.h5)",
    )
    ap.add_argument(
        "--manifest-csv",
        type=Path,
        default=None,
        help="Override manifest (default: <model-dir>/selected_trials.csv)",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output HDF5 (default: <model-dir>/training_exemplar_table.h5)",
    )
    ap.add_argument("--fps", type=float, default=30.0, help="FPS for pre/post frame counts")
    ap.add_argument("--exemplar-pre-seconds", type=float, default=0.167)
    ap.add_argument("--exemplar-post-seconds", type=float, default=0.5)
    ap.add_argument("--exemplar-min-frequency", type=float, default=0.0001)
    ap.add_argument("--exemplar-min-duration", type=int, default=1)
    ap.add_argument(
        "--exemplar-neighbors",
        type=int,
        default=42,
        help=(
            "Number of neighboring syllable instances to consider around each candidate exemplar "
            "when selecting diverse exemplars; higher values increase diversity but may slow processing."
        ),
    )
    ap.add_argument(
        "--no-density-sample",
        action="store_true",
        help="Disable density sampling when choosing syllable instances",
    )
    ap.add_argument(
        "--exemplar-arena-coords",
        action="store_true",
        help="Median in arena coordinates (not recommended for GIF-like motifs); default is ego-centered",
    )
    ap.add_argument(
        "--ignore-fit-summary-preprocess",
        action="store_true",
        help="Do not load KpmsPreprocessConfig from fit_summary.json",
    )
    ap.add_argument(
        "--retain-all-sleap-frames",
        action="store_true",
        help=(
            "Keep all SLEAP video frames in coordinates (NaN where invalid) so T matches "
            "native kpMS results.h5; required when results were fit on full-length sequences"
        ),
    )
    args = ap.parse_args()

    model_dir = Path(args.model_dir).resolve()
    results_h5 = Path(args.results_h5) if args.results_h5 else model_dir / "results.h5"
    out = Path(args.output) if args.output else model_dir / "training_exemplar_table.h5"

    if not results_h5.is_file():
        print(f"Missing training results: {results_h5}", file=sys.stderr)
        return 1

    if args.manifest_csv:
        from maze.pipeline.io.file_discovery import load_manifest_csv

        manifests = load_manifest_csv(Path(args.manifest_csv))
    else:
        manifests = load_selected_trials_manifests(model_dir)

    pre_cfg = KpmsPreprocessConfig()
    if not args.ignore_fit_summary_preprocess:
        loaded = _pre_cfg_from_fit_summary(model_dir)
        if loaded is not None:
            pre_cfg = loaded

    if args.retain_all_sleap_frames:
        pre_cfg = replace(pre_cfg, retain_all_frames=True)

    params = TrainingExemplarBuildParams(
        pre_seconds=float(args.exemplar_pre_seconds),
        post_seconds=float(args.exemplar_post_seconds),
        min_frequency=float(args.exemplar_min_frequency),
        min_duration=int(args.exemplar_min_duration),
        density_sample=not bool(args.no_density_sample),
        n_neighbors=int(args.exemplar_neighbors),
        fps=float(args.fps),
        projection_plane="xy",
        egocentric=not bool(args.exemplar_arena_coords),
    )

    typical = compute_training_typical_trajectories(
        results_h5=results_h5,
        manifests=manifests,
        pre_cfg=pre_cfg,
        params=params,
    )
    extra = {
        "model_dir": str(model_dir),
        "n_manifest_rows": len(manifests),
        "n_syllables": len(typical),
    }
    save_training_exemplar_table(
        out,
        typical,
        source_results_h5=results_h5,
        pre_cfg=pre_cfg,
        params=params,
        extra_meta=extra,
    )
    print(f"Wrote {out} ({len(typical)} syllables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
