#!/usr/bin/env python3
"""Build anatomical–blob–fused contrast sidecar from Phase I label tables (scratch).

Reads per-stream ``shared/hdbscan_labels*.csv`` under ``behavior_ethogram/phase_i/``
and writes ``contrast_sidecar*.csv`` at the phase_i root (ADR 0009).

Example::

    uv run python scratch/kpms_ensemble_compare/build_contrast_sidecar.py \\
        --kpms-root "C:/Users/admin/Documents/work/sack/test2" \\
        --phase all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRATCH_DIR = Path(__file__).resolve().parent
if str(_SCRATCH_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_DIR))

from behavior_ethogram_phase_i import (  # noqa: E402
    DEFAULT_LOW_CONTRAST_MPS,
    build_contrast_sidecar_from_dirs,
    contrast_sidecar_path,
    default_phase_i_out_dir,
    write_contrast_sidecar_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kpms-root", type=Path, default=None)
    parser.add_argument(
        "--phase-i-dir",
        type=Path,
        default=None,
        help="Phase I artifact root (default: {kpms_root}/behavior_ethogram/phase_i)",
    )
    parser.add_argument(
        "--phase",
        choices=("all", "run", "iti"),
        default="all",
    )
    parser.add_argument(
        "--low-contrast-mps",
        type=float,
        default=DEFAULT_LOW_CONTRAST_MPS,
        help="Speed delta below this is treated as low contrast for fused validation",
    )
    args = parser.parse_args()

    if args.phase_i_dir is None:
        if args.kpms_root is None:
            parser.error("Provide --phase-i-dir or --kpms-root")
        phase_i_dir = default_phase_i_out_dir(args.kpms_root.expanduser().resolve())
    else:
        phase_i_dir = args.phase_i_dir.expanduser().resolve()

    rows = build_contrast_sidecar_from_dirs(
        phase_i_dir,
        phase=args.phase,
        low_contrast_mps=args.low_contrast_mps,
    )
    out_path = contrast_sidecar_path(phase_i_dir, phase=args.phase)
    write_contrast_sidecar_csv(out_path, rows)
    print(f"Wrote {len(rows)} contrast rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
