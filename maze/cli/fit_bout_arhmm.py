"""CLI: fit Stage III bout AR-HMM and decode behavior tokens."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.behavior_ethogram.arhmm import (
    batch_trial_bout_sequences,
    build_trial_sequences_from_table,
    decode_behavior_tokens,
    fit_bout_arhmm,
)
from maze.kpms.behavior_ethogram.arhmm_config import BoutArhmmConfig
from maze.kpms.behavior_ethogram.bout_table_io import read_bout_table_csv, write_bout_table_csv
from maze.kpms.behavior_ethogram.paths import (
    arhmm_fit_summary_json,
    bout_features_clustered_csv,
    bout_tokens_csv,
    discover_anatomical_seeds,
    stage_iii_dir,
)
from maze.kpms.io import write_json


def _select_rows_for_fit(
    table: list[dict[str, str]],
    *,
    seed: str | None,
    pooled_cohort: bool,
) -> list[dict[str, str]]:
    if pooled_cohort:
        return table
    if seed is None:
        seeds = sorted({str(r["seed"]) for r in table})
        if len(seeds) != 1:
            raise ValueError(
                "Multiple seeds in bout table; pass --seed or use --pooled-cohort."
            )
        seed = seeds[0]
    return [r for r in table if str(r["seed"]) == str(seed)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fit bout AR-HMM (jax_moseq) and decode behavior tokens.")
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--stage-ii-dir", type=Path, default=None)
    ap.add_argument("--input-csv", type=Path, default=None)
    ap.add_argument("--seed", type=str, default=None, help="Interim per-seed fit (default when multiple seeds)")
    ap.add_argument("--pooled-cohort", action="store_true")
    ap.add_argument("--include-heading-direction", action="store_true")
    ap.add_argument(
        "--include-cluster-feature",
        action="store_true",
        help="Removed in S2 (syllable kinematic signatures replace cluster_id).",
    )
    ap.add_argument("--num-iters", type=int, default=200)
    ap.add_argument("--num-states", type=int, default=20)
    ap.add_argument("--nlags", type=int, default=2)
    ap.add_argument("--kappa", type=float, default=500.0)
    args = ap.parse_args(argv)

    if args.include_cluster_feature:
        print(
            "--include-cluster-feature was removed in S2; syllable kinematic signatures are used instead.",
            file=sys.stderr,
        )
        return 2

    kpms_root = Path(args.kpms_root)
    stage_ii = Path(args.stage_ii_dir) if args.stage_ii_dir else kpms_root / "behavior_ethogram" / "stage_ii"
    in_csv = Path(args.input_csv) if args.input_csv else bout_features_clustered_csv(stage_ii)
    if not in_csv.is_file():
        print(f"Missing clustered bout CSV: {in_csv}", file=sys.stderr)
        return 1

    table = read_bout_table_csv(in_csv)
    available_seeds = discover_anatomical_seeds(kpms_root)
    fit_seed = None if args.pooled_cohort else args.seed
    if fit_seed is None and not args.pooled_cohort and len(available_seeds) == 1:
        fit_seed = available_seeds[0]

    try:
        subset = _select_rows_for_fit(table, seed=fit_seed, pooled_cohort=args.pooled_cohort)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    sequences = build_trial_sequences_from_table(
        subset,
        include_heading_direction=args.include_heading_direction,
    )
    if not sequences:
        print("No trial bout sequences to fit.", file=sys.stderr)
        return 1

    batched = batch_trial_bout_sequences(sequences)
    cfg = BoutArhmmConfig(
        num_states=args.num_states,
        nlags=args.nlags,
        kappa=args.kappa,
        num_iters=args.num_iters,
    )
    fit_result = fit_bout_arhmm(batched, cfg)
    decoded = decode_behavior_tokens(
        fit_result.model, fit_result.scaled, nlags=cfg.nlags
    )

    token_lookup: dict[tuple[str, str, int], int] = {}
    for seed, trial_key, tokens in decoded:
        for bout_index, token in enumerate(tokens):
            token_lookup[(seed, trial_key, bout_index)] = int(token)

    out_rows: list[dict] = []
    for row in subset:
        key = (str(row["seed"]), str(row["trial_key"]), int(row["bout_index"]))
        out = dict(row)
        out["behavior_token"] = token_lookup.get(key, "")
        out_rows.append(out)

    out_stage_iii = stage_iii_dir(kpms_root, seed=None if args.pooled_cohort else fit_seed)
    write_bout_table_csv(bout_tokens_csv(out_stage_iii), out_rows)
    summary = {
        "fit_scope": "pooled" if args.pooled_cohort else "per_seed",
        "seed": fit_seed,
        "n_trials": len(sequences),
        "n_bouts": len(subset),
        "include_cluster_feature": False,
        "include_heading_direction": args.include_heading_direction,
        "hyperparams": cfg.to_json_dict(),
        "feature_zscore_mean": fit_result.feature_mean.tolist(),
        "feature_zscore_std": fit_result.feature_std.tolist(),
        "n_unique_behavior_tokens": len(
            {int(t) for _s, _k, toks in decoded for t in toks}
        ),
        "output_dir": str(out_stage_iii),
    }
    write_json(arhmm_fit_summary_json(out_stage_iii), summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
