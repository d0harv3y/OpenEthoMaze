"""Mine frequent syllable-bout n-grams for Option A grammar discovery."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .bout_scalars import syllable_runs
from .grammar_contract import CANDIDATE_SEQUENCE_FIELDS


@dataclass(frozen=True)
class MinedSequence:
    pattern: tuple[int, ...]
    count: int
    n_trials: int
    example_trial_keys: tuple[str, ...]


def bout_syllable_ids(z: Sequence[int] | Iterable[int]) -> list[int]:
    """Collapse a per-frame syllable stream to bout-level syllable ids."""
    arr = list(z)
    return [int(sid) for sid, _lo, _hi in syllable_runs(arr)]


def iter_ngrams(seq: Sequence[int], n: int) -> Iterable[tuple[int, ...]]:
    if n <= 0:
        return
    limit = len(seq) - n + 1
    for i in range(limit):
        yield tuple(int(x) for x in seq[i : i + n])


def mine_ngram_candidates(
    trial_sequences: Mapping[str, Sequence[int]],
    *,
    min_count: int = 2,
    max_n: int = 4,
    max_examples: int = 5,
) -> list[MinedSequence]:
    """Count bout-level n-grams across trials."""
    if max_n < 1:
        raise ValueError("max_n must be >= 1")
    counts: dict[tuple[int, ...], int] = defaultdict(int)
    trials_by_pattern: dict[tuple[int, ...], set[str]] = defaultdict(set)

    for trial_key, z in trial_sequences.items():
        bout_ids = bout_syllable_ids(z)
        seen_in_trial: set[tuple[int, ...]] = set()
        for n in range(1, max_n + 1):
            for pat in iter_ngrams(bout_ids, n):
                counts[pat] += 1
                if pat not in seen_in_trial:
                    trials_by_pattern[pat].add(str(trial_key))
                    seen_in_trial.add(pat)

    out: list[MinedSequence] = []
    for pat, count in counts.items():
        if count < min_count:
            continue
        trial_keys = tuple(sorted(trials_by_pattern[pat]))[:max_examples]
        out.append(
            MinedSequence(
                pattern=pat,
                count=int(count),
                n_trials=len(trials_by_pattern[pat]),
                example_trial_keys=trial_keys,
            )
        )
    out.sort(key=lambda m: (-m.count, -len(m.pattern), m.pattern))
    return out


def write_candidate_sequences_csv(path: Path | str, candidates: Sequence[MinedSequence]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(CANDIDATE_SEQUENCE_FIELDS))
        writer.writeheader()
        for cand in candidates:
            writer.writerow(
                {
                    "pattern_json": json.dumps(list(cand.pattern)),
                    "pattern_len": len(cand.pattern),
                    "count": cand.count,
                    "n_trials": cand.n_trials,
                    "example_trial_keys": ";".join(cand.example_trial_keys),
                    "behavior_name": "",
                    "notes": "",
                }
            )


def read_candidate_sequences_csv(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
