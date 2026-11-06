"""PROTOTYPE TUI — grammar candidate curation with anchor + scalar preview."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from curate_preview import (
    CurateState,
    assign_behavior_name,
    candidate_from_csv_row,
    demo_candidates,
    enrich_from_bout_features,
    prev_candidate,
    skip_candidate,
    summarize_current,
)

BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"


def _clear() -> None:
    print("\033[2J\033[H", end="")


def _load_candidates(path: Path) -> list:
    import csv

    with path.open(newline="", encoding="utf-8") as f:
        return [candidate_from_csv_row(r) for r in csv.DictReader(f)]


def _load_bout_rows(path: Path) -> list[dict[str, str]]:
    import csv

    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _anchor_moving_fraction(anchor_dir: Path | None) -> float:
    if anchor_dir is None or not anchor_dir.is_dir():
        return 0.35
    try:
        from maze.kpms.behavior_ethogram.anchor_store import read_is_moving_anchor

        anchor = read_is_moving_anchor(anchor_dir)
        vals = [bool(x) for t in anchor.trials for x in t.is_moving]
        return float(sum(vals) / len(vals)) if vals else 0.35
    except Exception:
        return 0.35


def render(state: CurateState) -> None:
    _clear()
    summary = summarize_current(state)
    print(f"{BOLD}PROTOTYPE{RESET} {DIM}grammar curation preview — throwaway{RESET}\n")
    for key, val in summary.items():
        if key == "bout_scalars" and isinstance(val, dict):
            print(f"{BOLD}{key}{RESET}")
            for sk, sv in val.items():
                print(f"  {DIM}{sk}{RESET}: {sv}")
        else:
            print(f"{BOLD}{key}{RESET}: {val}")
    print()
    print(f"{DIM}Harness only scores names in moving/still sets (see evaluate.py).{RESET}")
    print(f"{DIM}No grammar appendix contracted yet — is_moving is the sole anchor.{RESET}\n")
    print(f"{BOLD}[n]{RESET} name  {BOLD}[s]{RESET} skip  {BOLD}[p]{RESET} prev  {BOLD}[q]{RESET} quit")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PROTOTYPE: grammar candidate curation TUI")
    ap.add_argument("--candidates-csv", type=Path, default=None)
    ap.add_argument("--bout-features-csv", type=Path, default=None)
    ap.add_argument("--seed", type=str, default=None)
    ap.add_argument("--anchor-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.candidates_csv and args.candidates_csv.is_file():
        candidates = _load_candidates(args.candidates_csv)
    else:
        candidates = demo_candidates()

    if args.bout_features_csv and args.bout_features_csv.is_file():
        candidates = enrich_from_bout_features(candidates, _load_bout_rows(args.bout_features_csv), seed=args.seed)

    state = CurateState(
        candidates=candidates,
        anchor_moving_fraction=_anchor_moving_fraction(args.anchor_dir),
    )

    while True:
        render(state)
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        cmd = line[0].lower()
        if cmd == "q":
            break
        if cmd == "s":
            state = skip_candidate(state)
            continue
        if cmd == "p":
            state = prev_candidate(state)
            continue
        if cmd == "n":
            name = line[1:].strip() if len(line) > 1 else input("behavior_name: ").strip()
            if name:
                state = assign_behavior_name(state, name)
                state = skip_candidate(state)
            continue
        if cmd == "j":
            try:
                state = replace_index(state, int(line[1:].strip()) - 1)
            except ValueError:
                pass
            continue
        print(f"{DIM}unknown command{RESET}")

    print(json.dumps({"draft_rules": state.draft_rules}, indent=2))
    return 0


def replace_index(state: CurateState, index: int) -> CurateState:
    from dataclasses import replace

    if not state.candidates:
        return state
    index = max(0, min(index, len(state.candidates) - 1))
    return replace(state, index=index)


if __name__ == "__main__":
    # Allow running from repo root or prototype dir
    proto_dir = Path(__file__).resolve().parent
    if str(proto_dir) not in sys.path:
        sys.path.insert(0, str(proto_dir))
    raise SystemExit(main())
