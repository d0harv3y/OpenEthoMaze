"""Pure logic for grammar curation preview (PROTOTYPE — liftable into maze/)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Mapping, Sequence

# Mirror evaluate.py defaults (harness contract).
MOVING_NAMES = frozenset({"locomote", "fast_transit", "slow_explore", "turn_heavy", "moving"})
STILL_NAMES = frozenset({"pause", "still", "freeze", "immobile"})


@dataclass(frozen=True)
class CandidateRow:
    pattern: tuple[int, ...]
    count: int
    n_trials: int
    example_trial_keys: tuple[str, ...]
    behavior_name: str = ""
    notes: str = ""
    mean_speed_mps: float | None = None
    mean_abs_dheading: float | None = None
    mean_straightness: float | None = None
    mean_blob_area_px2: float | None = None


@dataclass
class CurateState:
    candidates: list[CandidateRow]
    index: int = 0
    draft_rules: list[tuple[tuple[int, ...], str]] = field(default_factory=list)
    anchor_moving_fraction: float = 0.35  # cohort prior if no anchor loaded

    @property
    def current(self) -> CandidateRow | None:
        if not self.candidates:
            return None
        return self.candidates[self.index]


def classify_name_for_anchor(name: str) -> str:
    """moving | still | unmapped"""
    key = name.strip().lower()
    if key in MOVING_NAMES:
        return "moving"
    if key in STILL_NAMES:
        return "still"
    return "unmapped"


def anchor_bucket_for_name(name: str) -> bool | None:
    cls = classify_name_for_anchor(name)
    if cls == "moving":
        return True
    if cls == "still":
        return False
    return None


def preview_anchor_scorable_fraction(name: str) -> float:
    """Fraction of curated rows that would score against is_moving (mapped names only)."""
    if not name.strip():
        return 0.0
    return 1.0 if anchor_bucket_for_name(name) is not None else 0.0


def estimate_agreement_if_all_matches(name: str, anchor_moving_fraction: float) -> float | None:
    """Naive: if every frame in matched spans carried this behavior_name, agreement vs anchor."""
    bucket = anchor_bucket_for_name(name)
    if bucket is None:
        return None
    # Perfect agreement when producer moving fraction equals anchor moving fraction
    # on frames where both are defined — prototype uses global anchor prior.
    prod_moving = 1.0 if bucket else 0.0
    return 1.0 - abs(prod_moving - anchor_moving_fraction)


def assign_behavior_name(state: CurateState, name: str) -> CurateState:
    cur = state.current
    if cur is None:
        return state
    updated = replace(cur, behavior_name=name.strip())
    candidates = list(state.candidates)
    candidates[state.index] = updated
    rules = list(state.draft_rules)
    if name.strip():
        rules.append((cur.pattern, name.strip()))
    return replace(state, candidates=candidates, draft_rules=rules)


def skip_candidate(state: CurateState) -> CurateState:
    if not state.candidates:
        return state
    return replace(state, index=min(state.index + 1, len(state.candidates) - 1))


def prev_candidate(state: CurateState) -> CurateState:
    if not state.candidates:
        return state
    return replace(state, index=max(state.index - 1, 0))


def summarize_current(state: CurateState) -> dict[str, object]:
    cur = state.current
    if cur is None:
        return {"status": "no candidates"}
    name = cur.behavior_name
    return {
        "index": f"{state.index + 1}/{len(state.candidates)}",
        "pattern": list(cur.pattern),
        "count": cur.count,
        "n_trials": cur.n_trials,
        "examples": list(cur.example_trial_keys),
        "behavior_name": name or "(unset)",
        "anchor_class": classify_name_for_anchor(name) if name else "unset",
        "harness_scorable": preview_anchor_scorable_fraction(name),
        "naive_anchor_agreement": estimate_agreement_if_all_matches(name, state.anchor_moving_fraction),
        "bout_scalars": {
            "mean_speed_mps": cur.mean_speed_mps,
            "mean_abs_dheading": cur.mean_abs_dheading,
            "mean_straightness": cur.mean_straightness,
            "mean_blob_area_px2": cur.mean_blob_area_px2,
        },
        "draft_rules": len(state.draft_rules),
        "pose_note": (
            "Scalars summarize locomotion/blob; syllable id carries egocentric pose. "
            "Same syllable in different contexts needs multi-bout patterns or exemplar movies."
        ),
    }


def candidate_from_csv_row(row: Mapping[str, str]) -> CandidateRow:
    pattern = tuple(int(x) for x in json.loads(row["pattern_json"]))
    examples = tuple(k for k in str(row.get("example_trial_keys", "")).split(";") if k)
    return CandidateRow(
        pattern=pattern,
        count=int(row["count"]),
        n_trials=int(row["n_trials"]),
        example_trial_keys=examples,
        behavior_name=str(row.get("behavior_name", "")).strip(),
        notes=str(row.get("notes", "")).strip(),
    )


def enrich_from_bout_features(
    candidates: Sequence[CandidateRow],
    bout_rows: Sequence[Mapping[str, str]],
    *,
    seed: str | None = None,
) -> list[CandidateRow]:
    """Pool bout scalar means for bouts whose trial bout sequence contains the pattern."""
    by_trial: dict[str, list[tuple[int, Mapping[str, str]]]] = {}
    for row in bout_rows:
        if seed is not None and str(row.get("seed", "")) != str(seed):
            continue
        tk = str(row["trial_key"])
        by_trial.setdefault(tk, []).append((int(row["bout_index"]), row))

    def trial_bout_ids(trial_key: str) -> list[int]:
        items = sorted(by_trial.get(trial_key, []), key=lambda t: t[0])
        return [int(r["raw_syllable_id"]) for _i, r in items]

    def match_spans(bout_ids: list[int], pattern: tuple[int, ...]) -> list[int]:
        """Return bout indices where pattern matches (start index)."""
        n = len(pattern)
        hits: list[int] = []
        for i in range(len(bout_ids) - n + 1):
            if tuple(bout_ids[i : i + n]) == pattern:
                hits.append(i)
        return hits

    out: list[CandidateRow] = []
    for cand in candidates:
        speeds: list[float] = []
        dheads: list[float] = []
        straights: list[float] = []
        areas: list[float] = []
        for tk in cand.example_trial_keys or tuple(by_trial.keys()):
            bout_ids = trial_bout_ids(tk)
            items = sorted(by_trial.get(tk, []), key=lambda t: t[0])
            for start in match_spans(bout_ids, cand.pattern):
                for j in range(start, start + len(cand.pattern)):
                    _bi, r = items[j]
                    speeds.append(float(r["bout_mean_speed_mps"]))
                    dheads.append(float(r["bout_mean_abs_dheading"]))
                    straights.append(float(r["bout_straightness"]))
                    areas.append(float(r["bout_mean_blob_area_px2"]))
        if not speeds:
            out.append(cand)
            continue
        import numpy as np

        out.append(
            replace(
                cand,
                mean_speed_mps=float(np.mean(speeds)),
                mean_abs_dheading=float(np.mean(dheads)),
                mean_straightness=float(np.mean(straights)),
                mean_blob_area_px2=float(np.mean(areas)),
            )
        )
    return out


def demo_candidates() -> list[CandidateRow]:
    return [
        CandidateRow((12,), 400, 80, ("3243/S01/T01", "3243/S01/T02"), mean_speed_mps=0.04, mean_straightness=0.2),
        CandidateRow((3, 7, 7), 120, 35, ("3243/S02/T01",), mean_speed_mps=0.09, mean_straightness=0.85),
        CandidateRow((5, 5, 2), 90, 28, ("3243/S03/T01",), mean_speed_mps=0.15, mean_abs_dheading=0.4),
    ]
