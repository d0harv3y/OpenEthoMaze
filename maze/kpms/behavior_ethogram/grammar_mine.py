"""Mine frequent syllable-bout n-grams for Option A grammar discovery."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from .grammar_contract import CANDIDATE_SEQUENCE_FIELDS


@dataclass(frozen=True)
class MinedSequence:
    pattern: tuple[int, ...]
    count: int
    n_trials: int
    example_trial_keys: tuple[str, ...]
    example_matches_json: str = ""
    mean_speed_mps: float | None = None
    mean_abs_dheading: float | None = None
    mean_straightness: float | None = None
    mean_blob_area_px2: float | None = None
    must_review_overlay: bool = False
    behavior_name: str = ""
    anchor_bucket: str = ""
    reviewed_at: str = ""
    reviewed_trial_key: str = ""
    notes: str = ""


def bout_syllable_ids(z: Sequence[int] | Iterable[int] | np.ndarray) -> list[int]:
    """Collapse a per-frame syllable stream to bout-level syllable ids."""
    from .bout_scalars import syllable_runs

    arr = np.asarray(list(z) if not isinstance(z, np.ndarray) else z, dtype=np.int64)
    return [int(sid) for sid, _lo, _hi in syllable_runs(arr)]


def bout_syllable_id_array(z: Sequence[int] | np.ndarray) -> np.ndarray:
    """Bout-level syllable ids as a 1-D int64 array."""
    return np.asarray(bout_syllable_ids(z), dtype=np.int64)


def iter_ngrams(seq: Sequence[int], n: int) -> Iterable[tuple[int, ...]]:
    if n <= 0:
        return
    limit = len(seq) - n + 1
    for i in range(limit):
        yield tuple(int(x) for x in seq[i : i + n])


def _count_trial_ngrams(
    bout_ids: np.ndarray,
    *,
    max_n: int,
    counts: dict[tuple[int, ...], int],
    trials_by_pattern: dict[tuple[int, ...], set[str]],
    trial_key: str,
    seen_in_trial: set[tuple[int, ...]],
) -> None:
    n_bouts = int(len(bout_ids))
    if n_bouts == 0:
        return
    for n in range(1, max_n + 1):
        if n_bouts < n:
            continue
        windows = sliding_window_view(bout_ids, n)
        for window in windows:
            pat = tuple(int(x) for x in window)
            counts[pat] += 1
            if pat not in seen_in_trial:
                trials_by_pattern[pat].add(trial_key)
                seen_in_trial.add(pat)


def mine_ngram_candidates(
    trial_sequences: Mapping[str, Sequence[int] | np.ndarray],
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
        bout_ids = bout_syllable_id_array(z)
        seen_in_trial: set[tuple[int, ...]] = set()
        _count_trial_ngrams(
            bout_ids,
            max_n=max_n,
            counts=counts,
            trials_by_pattern=trials_by_pattern,
            trial_key=str(trial_key),
            seen_in_trial=seen_in_trial,
        )

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


def _fmt_float(val: float | None) -> str:
    if val is None:
        return ""
    return str(float(val))


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
                    "mean_speed_mps": _fmt_float(cand.mean_speed_mps),
                    "mean_abs_dheading": _fmt_float(cand.mean_abs_dheading),
                    "mean_straightness": _fmt_float(cand.mean_straightness),
                    "mean_blob_area_px2": _fmt_float(cand.mean_blob_area_px2),
                    "must_review_overlay": int(bool(cand.must_review_overlay)),
                    "behavior_name": cand.behavior_name,
                    "anchor_bucket": cand.anchor_bucket,
                    "reviewed_at": cand.reviewed_at,
                    "reviewed_trial_key": cand.reviewed_trial_key,
                    "notes": cand.notes,
                }
            )


def read_candidate_sequences_csv(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_candidate_artifacts(
    grammar_dir: Path | str,
    candidates: Sequence[MinedSequence],
    *,
    fit_id: str,
) -> tuple[Path, Path]:
    """Write lean CSV plus verbose exemplar sidecar."""
    from .grammar_exemplars import write_candidate_exemplars_json
    from .paths import grammar_candidate_exemplars_json, grammar_candidates_csv

    gdir = Path(grammar_dir)
    csv_path = grammar_candidates_csv(gdir)
    exemplars_path = grammar_candidate_exemplars_json(gdir)
    write_candidate_sequences_csv(csv_path, candidates)
    write_candidate_exemplars_json(exemplars_path, candidates, fit_id=fit_id)
    return csv_path, exemplars_path
