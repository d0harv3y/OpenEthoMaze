#!/usr/bin/env python3
"""Calibrate Phase II locomotion tiers from anatomical Phase I labels (scratch).

Reads ``anatomical/shared/hdbscan_labels*.csv``, assigns tiers via YAML rules on
token centroids, writes ``locomotion_tiers.yaml``, ``token_tiers*.csv``, and
calibration histograms under ``behavior_ethogram/phase_ii/`` (ADR 0009).

Example::

    uv run python scratch/kpms_ensemble_compare/calibrate_locomotion_tiers.py \\
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
    default_phase_i_out_dir,
    hdbscan_labels_path,
)
from behavior_ethogram_phase_ii import (  # noqa: E402
    DEFAULT_LOCOMOTION_RULES,
    calibration_summary_path,
    calibrate_from_phase_i,
    default_phase_ii_out_dir,
    load_locomotion_rules_yaml,
    load_prototype_label_rows,
    locomotion_tiers_yaml_path,
    render_calibration_plots,
    token_tiers_csv_path,
    write_calibration_summary,
    write_locomotion_rules_yaml,
    write_token_tiers_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kpms-root", type=Path, default=None)
    parser.add_argument(
        "--phase-i-dir",
        type=Path,
        default=None,
        help="Phase I root (default: {kpms_root}/behavior_ethogram/phase_i)",
    )
    parser.add_argument(
        "--phase-ii-dir",
        type=Path,
        default=None,
        help="Phase II output root (default: {kpms_root}/behavior_ethogram/phase_ii)",
    )
    parser.add_argument(
        "--phase",
        choices=("all", "run", "iti"),
        default="all",
    )
    parser.add_argument(
        "--rules-yaml",
        type=Path,
        default=None,
        help="Optional tier rules YAML (default: ship v1 defaults)",
    )
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()

    if args.phase_i_dir is None:
        if args.kpms_root is None:
            parser.error("Provide --phase-i-dir or --kpms-root")
        phase_i_dir = default_phase_i_out_dir(args.kpms_root.expanduser().resolve())
    else:
        phase_i_dir = args.phase_i_dir.expanduser().resolve()

    if args.phase_ii_dir is not None:
        phase_ii_dir = args.phase_ii_dir.expanduser().resolve()
    elif args.kpms_root is not None:
        phase_ii_dir = default_phase_ii_out_dir(args.kpms_root.expanduser().resolve())
    else:
        phase_ii_dir = phase_i_dir.parent / "phase_ii"

    if args.rules_yaml is not None:
        rules_doc = load_locomotion_rules_yaml(args.rules_yaml.expanduser().resolve())
    else:
        rules_doc = DEFAULT_LOCOMOTION_RULES

    token_rows, _centroids, _tier_by_cluster, summary = calibrate_from_phase_i(
        phase_i_dir,
        phase=args.phase,
        rules_doc=rules_doc,
    )
    yaml_path = locomotion_tiers_yaml_path(phase_ii_dir)
    write_locomotion_rules_yaml(yaml_path, rules_doc)
    token_path = token_tiers_csv_path(phase_ii_dir, phase=args.phase)
    write_token_tiers_csv(token_path, token_rows)

    summary_path = calibration_summary_path(phase_ii_dir, phase=args.phase)
    write_calibration_summary(summary_path, summary)

    plot_paths: list[Path] = []
    if not args.no_plots:
        prototypes = load_prototype_label_rows(
            hdbscan_labels_path(phase_i_dir, "anatomical", phase=args.phase),
        )
        plot_paths = render_calibration_plots(summary_path.parent, prototypes, token_rows)

    print(f"Wrote {len(token_rows)} token tier rows -> {token_path}")
    print(f"Wrote rules -> {yaml_path}")
    print(f"Wrote calibration summary -> {summary_path}")
    for path in plot_paths:
        print(f"Wrote plot -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
