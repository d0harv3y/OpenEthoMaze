"""CLI: summarize behavior-token occupancy and transitions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.behavior_ethogram.behavior_token_labels import read_behavior_token_labels_csv
from maze.kpms.behavior_ethogram.behavior_token_summarize import (
    PhaseName,
    resolve_token_to_label,
    summarize_behavior_tokens,
    summarize_bout_rows_from_table,
    write_summary_csv,
)
from maze.kpms.behavior_ethogram.behavior_token_summarize_contract import (
    BEHAVIOR_TOKEN_SUMMARIZE_SCHEMA,
    OCCUPANCY_FIELDS,
    TRANSITION_FIELDS,
)
from maze.kpms.behavior_ethogram.bout_table_io import read_bout_table_csv
from maze.kpms.behavior_ethogram.paths import (
    behavior_token_labels_csv,
    bout_tokens_csv,
    resolve_stage_iii_dir,
    token_occupancy_by_session_csv,
    token_occupancy_csv,
    token_summaries_dir,
    token_transitions_csv,
)
from maze.kpms.frame_alignment import kpms_recording_key
from maze.pipeline.io.file_discovery import load_manifest_csv


def _parse_phases(raw: str) -> list[PhaseName]:
    value = raw.strip().lower()
    if value == "all":
        return ["run", "iti"]
    if value in {"run", "iti"}:
        return [value]  # type: ignore[list-item]
    raise ValueError(f"unsupported phase: {raw!r}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Summarize behavior-token occupancy and bout transitions (Stage III)."
    )
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--seed", type=str, required=True)
    ap.add_argument("--manifest-path", type=Path, required=True)
    ap.add_argument("--stage-iii-dir", type=Path, default=None)
    ap.add_argument("--tokens-csv", type=Path, default=None)
    ap.add_argument("--labels-csv", type=Path, default=None)
    ap.add_argument("--grain", choices=("token", "ethology"), required=True)
    ap.add_argument("--phase", choices=("run", "iti", "all"), default="run")
    ap.add_argument(
        "--min-token-bouts",
        type=int,
        default=20,
        help="Ethology review gate: tokens with at least this many bouts need curation",
    )
    ap.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow ethology grain with incomplete curation (unlabeled tokens become token_<id>)",
    )
    ap.add_argument(
        "--deliverable",
        choices=("occupancy", "occupancy_by_session", "transitions", "all"),
        default="all",
    )
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.stage_iii_dir is not None:
        stage_iii = Path(args.stage_iii_dir)
    else:
        stage_iii = resolve_stage_iii_dir(Path(args.kpms_root), seed=args.seed)

    tokens_path = Path(args.tokens_csv) if args.tokens_csv else bout_tokens_csv(stage_iii)
    if not tokens_path.is_file():
        print(f"Missing bout tokens CSV: {tokens_path}", file=sys.stderr)
        return 1

    manifests = load_manifest_csv(Path(args.manifest_path))
    manifests_by_trial_key = {kpms_recording_key(m): m for m in manifests}

    table = read_bout_table_csv(tokens_path)
    bout_rows = summarize_bout_rows_from_table(table, seed=args.seed)
    if not bout_rows:
        print(f"No bout token rows for seed {args.seed!r} in {tokens_path}", file=sys.stderr)
        return 1

    label_rows: list[dict[str, str]] | None = None
    labels_path = Path(args.labels_csv) if args.labels_csv else behavior_token_labels_csv(stage_iii)
    if args.grain == "ethology" or labels_path.is_file():
        if labels_path.is_file():
            label_rows = read_behavior_token_labels_csv(labels_path)
        elif args.grain == "ethology":
            print(f"Missing behavior token labels CSV: {labels_path}", file=sys.stderr)
            return 1

    try:
        phases = _parse_phases(args.phase)
        token_to_label = resolve_token_to_label(
            bout_rows,
            label_rows,
            grain=args.grain,
            allow_partial=bool(args.allow_partial),
            min_token_bouts=int(args.min_token_bouts),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    occupancy_rows, occupancy_session_rows, transition_rows = summarize_behavior_tokens(
        bout_rows=bout_rows,
        manifests_by_trial_key=manifests_by_trial_key,
        grain=args.grain,
        phases=phases,
        token_to_label=token_to_label,
    )

    out_dir = Path(args.out_dir) if args.out_dir else token_summaries_dir(stage_iii)
    written: dict[str, str] = {}
    deliverable = args.deliverable
    if deliverable in {"occupancy", "all"}:
        path = write_summary_csv(
            token_occupancy_csv(out_dir),
            occupancy_rows,
            fieldnames=OCCUPANCY_FIELDS,
        )
        written["occupancy_csv"] = str(path.resolve())
    if deliverable in {"occupancy_by_session", "all"}:
        path = write_summary_csv(
            token_occupancy_by_session_csv(out_dir),
            occupancy_session_rows,
            fieldnames=OCCUPANCY_FIELDS,
        )
        written["occupancy_by_session_csv"] = str(path.resolve())
    if deliverable in {"transitions", "all"}:
        path = write_summary_csv(
            token_transitions_csv(out_dir),
            transition_rows,
            fieldnames=TRANSITION_FIELDS,
        )
        written["transitions_csv"] = str(path.resolve())

    payload = {
        "schema": BEHAVIOR_TOKEN_SUMMARIZE_SCHEMA,
        "seed": str(args.seed),
        "grain": args.grain,
        "phase": args.phase,
        "deliverable": deliverable,
        "n_bout_rows": len(bout_rows),
        "n_manifest_trials": len(manifests_by_trial_key),
        "bout_tokens_csv": str(tokens_path.resolve()),
        "labels_csv": str(labels_path.resolve()) if labels_path.is_file() else None,
        "summaries_dir": str(out_dir.resolve()),
        **written,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
