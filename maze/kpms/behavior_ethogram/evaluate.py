"""Evaluate Behavior producers against the is_moving anchor (S1 harness, ADR-0004)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from maze.kpms.behavior_ethogram.anchor_store import IsMovingAnchor, read_is_moving_anchor
from maze.kpms.behavior_ethogram.labeling import read_behavior_labeling

DEFAULT_MOVING_BEHAVIOR_NAMES = frozenset({"locomote", "fast_transit", "slow_explore", "turn_heavy", "moving"})
DEFAULT_STILL_BEHAVIOR_NAMES = frozenset({"pause", "still", "freeze", "immobile"})


@dataclass(frozen=True)
class TrialEvaluation:
    trial_key: str
    n_joined_frames: int
    anchor_agreement: float
    producer_moving_fraction: float
    anchor_moving_fraction: float


@dataclass(frozen=True)
class EvaluationReport:
    producer: str
    fit_id: str
    n_trials: int
    mean_anchor_agreement: float
    mean_producer_moving_fraction: float
    mean_anchor_moving_fraction: float
    kinematic_validity_r: float
    trials: tuple[TrialEvaluation, ...]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["trials"] = [asdict(t) for t in self.trials]
        return d


@dataclass(frozen=True)
class CrossSeedReport:
    n_producers: int
    shared_trial_keys: tuple[str, ...]
    mean_moving_fraction_std: float
    per_producer_moving_fraction: dict[str, float]


def _anchor_lookup(anchor: IsMovingAnchor) -> dict[str, dict[int, bool]]:
    out: dict[str, dict[int, bool]] = {}
    for trial in anchor.trials:
        out[trial.trial_key] = {int(fi): bool(mv) for fi, mv in zip(trial.source_frame_index, trial.is_moving, strict=True)}
    return out


def _behavior_is_moving_from_bucket(bucket: str) -> bool | None:
    b = str(bucket).strip().lower()
    if b == "moving":
        return True
    if b == "still":
        return False
    return None


def _behavior_is_moving(
    behavior_id: int,
    behavior_names: Mapping[int, str],
    *,
    moving_names: frozenset[str],
    still_names: frozenset[str],
) -> bool | None:
    name = str(behavior_names.get(int(behavior_id), "")).strip().lower()
    if name in moving_names:
        return True
    if name in still_names:
        return False
    return None


def _resolve_behavior_moving(
    behavior_id: int,
    behavior_names: Mapping[int, str],
    behavior_anchor_buckets: Mapping[int, str],
    *,
    moving_names: frozenset[str],
    still_names: frozenset[str],
) -> bool | None:
    bucket = behavior_anchor_buckets.get(int(behavior_id))
    if bucket:
        resolved = _behavior_is_moving_from_bucket(bucket)
        if resolved is not None or str(bucket).strip().lower() == "ignore":
            return resolved
    return _behavior_is_moving(
        behavior_id,
        behavior_names,
        moving_names=moving_names,
        still_names=still_names,
    )


def evaluate_behavior_producer(
    producer_dir: Path | str,
    anchor_dir: Path | str,
    *,
    moving_names: frozenset[str] = DEFAULT_MOVING_BEHAVIOR_NAMES,
    still_names: frozenset[str] = DEFAULT_STILL_BEHAVIOR_NAMES,
) -> EvaluationReport:
    """Score one producer artifact dir against an on-disk anchor (file seam only)."""
    labeling = read_behavior_labeling(producer_dir)
    anchor = read_is_moving_anchor(anchor_dir)
    anchor_by_trial = _anchor_lookup(anchor)

    trial_rows: list[TrialEvaluation] = []
    agreements: list[float] = []
    prod_fracs: list[float] = []
    anchor_fracs: list[float] = []

    for trial in labeling.trials:
        amap = anchor_by_trial.get(trial.trial_key)
        if amap is None:
            continue
        matches = 0
        scored = 0
        prod_moving = 0
        anchor_moving = 0
        joined = 0
        for fi, bid in zip(trial.source_frame_index, trial.behavior_id, strict=True):
            if int(fi) not in amap:
                continue
            joined += 1
            anchor_mv = amap[int(fi)]
            if anchor_mv:
                anchor_moving += 1
            expected = _resolve_behavior_moving(
                int(bid),
                labeling.behavior_names,
                labeling.behavior_anchor_buckets,
                moving_names=moving_names,
                still_names=still_names,
            )
            if expected is None:
                continue
            scored += 1
            if expected:
                prod_moving += 1
            if expected == anchor_mv:
                matches += 1
        if joined == 0:
            continue
        agreement = float(matches / scored) if scored else float("nan")
        trial_rows.append(
            TrialEvaluation(
                trial_key=trial.trial_key,
                n_joined_frames=joined,
                anchor_agreement=agreement,
                producer_moving_fraction=float(prod_moving / scored) if scored else float("nan"),
                anchor_moving_fraction=float(anchor_moving / joined),
            )
        )
        if scored:
            agreements.append(agreement)
            prod_fracs.append(float(prod_moving / scored))
        anchor_fracs.append(float(anchor_moving / joined))

    def _mean(vals: list[float]) -> float:
        return float(np.nanmean(vals)) if vals else float("nan")

    def _validity_r(rows: Sequence[TrialEvaluation]) -> float:
        pairs = [
            (t.producer_moving_fraction, t.anchor_moving_fraction)
            for t in rows
            if np.isfinite(t.producer_moving_fraction) and np.isfinite(t.anchor_moving_fraction)
        ]
        if len(pairs) < 2:
            return float("nan")
        prod, anchor = zip(*pairs, strict=True)
        return float(np.corrcoef(prod, anchor)[0, 1])

    return EvaluationReport(
        producer=labeling.producer,
        fit_id=labeling.fit_id,
        n_trials=len(trial_rows),
        mean_anchor_agreement=_mean(agreements),
        mean_producer_moving_fraction=_mean(prod_fracs),
        mean_anchor_moving_fraction=_mean(anchor_fracs),
        kinematic_validity_r=_validity_r(trial_rows),
        trials=tuple(trial_rows),
    )


def evaluate_behavior_producers(
    producer_dirs: Sequence[Path | str],
    anchor_dir: Path | str,
    *,
    moving_names: frozenset[str] = DEFAULT_MOVING_BEHAVIOR_NAMES,
    still_names: frozenset[str] = DEFAULT_STILL_BEHAVIOR_NAMES,
) -> tuple[EvaluationReport, ...]:
    """Score each producer dir; harness never imports producer modules."""
    return tuple(
        evaluate_behavior_producer(
            d,
            anchor_dir,
            moving_names=moving_names,
            still_names=still_names,
        )
        for d in producer_dirs
    )


def cross_seed_reproducibility(reports: Sequence[EvaluationReport]) -> CrossSeedReport:
    """Compare producer moving fractions across fits on shared trial keys."""
    if not reports:
        return CrossSeedReport(0, (), float("nan"), {})
    by_trial: dict[str, list[tuple[str, float]]] = {}
    per_prod: dict[str, float] = {}
    for rep in reports:
        key = f"{rep.producer}/{rep.fit_id}"
        fracs = [t.producer_moving_fraction for t in rep.trials if np.isfinite(t.producer_moving_fraction)]
        per_prod[key] = float(np.mean(fracs)) if fracs else float("nan")
        for t in rep.trials:
            if np.isfinite(t.producer_moving_fraction):
                by_trial.setdefault(t.trial_key, []).append((key, t.producer_moving_fraction))

    shared = tuple(sorted(k for k, v in by_trial.items() if len(v) >= 2))
    stds: list[float] = []
    for tk in shared:
        vals = [v for _k, v in by_trial[tk]]
        stds.append(float(np.std(vals)))
    return CrossSeedReport(
        n_producers=len(reports),
        shared_trial_keys=shared,
        mean_moving_fraction_std=float(np.mean(stds)) if stds else float("nan"),
        per_producer_moving_fraction=per_prod,
    )
