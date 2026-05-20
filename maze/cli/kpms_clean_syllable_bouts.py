"""
Temporal bout cleanup on syllable label sequences (after semantic merge).

Use a YAML/JSON config with ``preset`` or explicit ``steps``, or pass ``--preset`` only.

Example::

    uv run maze-kpms-clean-syllable-bouts ^
      --results-h5 results_merged.h5 ^
      --preset conservative ^
      --output-h5 results_final.h5

Requires ``uv sync --extra kpms``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from maze.kpms.syllable_bout_clean import (
    apply_bout_pipeline_to_results,
    expand_preset,
    load_pipeline_config,
    save_bout_cleaned_results_h5,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Drop short syllable runs / bridge gaps (configurable).")
    ap.add_argument("--results-h5", type=Path, required=True)
    ap.add_argument("--output-h5", type=Path, required=True)
    ap.add_argument(
        "--config",
        type=Path,
        default=None,
        help="YAML/JSON with 'preset' or 'steps' and optional 'fps'",
    )
    ap.add_argument(
        "--preset",
        type=str,
        default=None,
        choices=("conservative", "drop_only", "movement_like", "movement-like"),
        help="Ignored if --config provides preset/steps",
    )
    ap.add_argument(
        "--fps",
        type=float,
        default=None,
        help="Override frames per second for step timing (default: 30, or value from --config)",
    )
    args = ap.parse_args()

    src = Path(args.results_h5)
    if not src.is_file():
        print(f"Missing {src}", file=sys.stderr)
        return 1

    cfg_path = Path(args.config) if args.config else None
    preset_name: str | None = None
    if cfg_path is not None and cfg_path.is_file():
        steps, fps = load_pipeline_config(cfg_path)
    elif args.preset:
        steps = expand_preset(str(args.preset))
        fps = 30.0
        preset_name = str(args.preset)
        cfg_path = None
    else:
        print("Provide --config <file> or --preset conservative|movement_like", file=sys.stderr)
        return 1

    if args.fps is not None:
        fps = float(args.fps)

    import keypoint_moseq as kpms

    results = kpms.load_hdf5(str(src))
    new_results = apply_bout_pipeline_to_results(results, fps=fps, steps=steps)
    save_bout_cleaned_results_h5(
        Path(args.output_h5),
        new_results,
        source_h5=src,
        steps=steps,
        fps=fps,
        config_path=cfg_path,
        preset=preset_name,
    )
    print(f"Wrote {args.output_h5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
