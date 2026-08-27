"""Analyze empty bout_mean_duty/dist in stimulus_bout_features.csv."""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

CSV = Path(
    r"C:\Users\admin\Documents\work\sack\gerstner_vast_fit\behavior_ethogram\stimulus_mi\stimulus_bout_features.csv"
)


@dataclass
class BoutRow:
    trial_key: str
    bout_index: int
    row_start: int
    row_end_exclusive: int
    bout_frames: int
    bout_primary_state: str
    duty: str
    dist: str

    @property
    def empty_stim(self) -> bool:
        return not self.duty.strip() or not self.dist.strip()


def load_rows(path: Path) -> list[BoutRow]:
    out: list[BoutRow] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(
                BoutRow(
                    trial_key=row["trial_key"],
                    bout_index=int(row["bout_index"]),
                    row_start=int(row["row_start"]),
                    row_end_exclusive=int(row["row_end_exclusive"]),
                    bout_frames=int(row["bout_frames"]),
                    bout_primary_state=row.get("bout_primary_state", ""),
                    duty=row.get("bout_mean_duty", ""),
                    dist=row.get("bout_mean_dist_px", ""),
                )
            )
    return out


def main() -> None:
    rows = load_rows(CSV)
    n = len(rows)
    empty = [r for r in rows if r.empty_stim]
    print(f"total bouts: {n}")
    print(f"empty stimulus: {len(empty)} ({100 * len(empty) / n:.2f}%)")

    by_trial: dict[str, list[BoutRow]] = defaultdict(list)
    for r in rows:
        by_trial[r.trial_key].append(r)

    trials_with_empty = 0
    tail_only = 0
    mixed = 0
    position_stats: list[tuple[float, float]] = []

    for trial_key, trial_rows in by_trial.items():
        trial_rows.sort(key=lambda r: r.bout_index)
        empties = [r for r in trial_rows if r.empty_stim]
        if not empties:
            continue
        trials_with_empty += 1
        max_bout = trial_rows[-1].bout_index
        max_row_end = trial_rows[-1].row_end_exclusive
        first_empty = min(r.bout_index for r in empties)
        all_tail = all(r.bout_index >= first_empty for r in empties)
        if all_tail and first_empty > 0:
            tail_only += 1
        else:
            mixed += 1
        for r in empties:
            position_stats.append((r.bout_index / max(max_bout, 1), r.row_end_exclusive / max(max_row_end, 1)))

    print(f"trials with any empty: {trials_with_empty} / {len(by_trial)}")
    print(f"empty only in tail (after first non-empty bout): {tail_only}")
    print(f"empty mixed with non-empty: {mixed}")

    if position_stats:
        bout_frac = sum(x for x, _ in position_stats) / len(position_stats)
        row_frac = sum(y for _, y in position_stats) / len(position_stats)
        print(f"mean bout_index fraction for empty rows: {bout_frac:.3f}")
        print(f"mean row_end_exclusive fraction for empty rows: {row_frac:.3f}")

    # Sample one trial with tail empties
    for trial_key, trial_rows in sorted(by_trial.items()):
        trial_rows.sort(key=lambda r: r.bout_index)
        if not any(r.empty_stim for r in trial_rows):
            continue
        if not all(r.empty_stim for r in trial_rows[-3:]):
            continue
        print("\n--- sample trial", trial_key, "---")
        for r in trial_rows[-8:]:
            flag = "EMPTY" if r.empty_stim else "ok"
            print(
                f"  bout {r.bout_index:3d} rows [{r.row_start:5d},{r.row_end_exclusive:5d}) "
                f"state={r.bout_primary_state!r:10s} duty={r.duty!s:12s} {flag}"
            )
        break

    # State breakdown for empty rows
    state_counts: dict[str, int] = defaultdict(int)
    for r in empty:
        state_counts[r.bout_primary_state or "(blank)"] += 1
    print("\nempty rows by bout_primary_state:")
    for state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")


if __name__ == "__main__":
    main()
