"""Enrich grammar candidates with bout scalars and overlay review flags (S3.1)."""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping, Sequence

import numpy as np

from .bout_scalars import DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS
from .grammar_contract import (
    OVERLAY_HIGH_DHEADING,
    OVERLAY_LOW_SPEED_MPS,
    OVERLAY_SPEED_GRAY_HI_MPS,
    OVERLAY_SPEED_GRAY_LO_MPS,
    normalize_anchor_bucket,
)
from .grammar_mine import MinedSequence


def _trial_bout_table(
    bout_rows: Sequence[Mapping[str, str]],
    *,
    seed: str | None,
) -> dict[str, list[tuple[int, Mapping[str, str]]]]:
    by_trial: dict[str, list[tuple[int, Mapping[str, str]]]] = {}
    for row in bout_rows:
        if seed is not None and str(row.get("seed", "")) != str(seed):
            continue
        tk = str(row["trial_key"])
        by_trial.setdefault(tk, []).append((int(row["bout_index"]), row))
    for tk in by_trial:
        by_trial[tk].sort(key=lambda t: t[0])
    return by_trial


def _pattern_match_bout_rows(
    pattern: tuple[int, ...],
    trial_key: str,
    by_trial: Mapping[str, list[tuple[int, Mapping[str, str]]]],
) -> list[Mapping[str, str]]:
    items = by_trial.get(trial_key, [])
    if not items:
        return []
    bout_ids = [int(r["raw_syllable_id"]) for _i, r in items]
    n = len(pattern)
    matched: list[Mapping[str, str]] = []
    for start in range(len(bout_ids) - n + 1):
        if tuple(bout_ids[start : start + n]) == pattern:
            for j in range(start, start + n):
                matched.append(items[j][1])
    return matched


def _opt_float(row: Mapping[str, str], key: str) -> float | None:
    """Parse an optional float cell; return None when absent or blank."""
    raw = row.get(key)
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _circular_mean(headings: Sequence[float]) -> float | None:
    """Circular mean of angles in radians; None when no finite samples."""
    arr = np.asarray(headings, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    mean = float(np.arctan2(np.mean(np.sin(arr)), np.mean(np.cos(arr))))
    return mean if np.isfinite(mean) else None


def enrich_candidates_with_bout_scalars(
    candidates: Sequence[MinedSequence],
    bout_rows: Sequence[Mapping[str, str]],
    *,
    seed: str | None = None,
    trial_keys: Sequence[str] | None = None,
) -> list[MinedSequence]:
    """Pool bout scalar means for each candidate pattern over all matched bouts.

    Pooling spans the full corpus of trials that contain the pattern (not just
    the capped ``example_trial_keys``) so the reported means reflect every
    matched bout. ``trial_keys`` narrows the corpus when provided.
    """
    by_trial = _trial_bout_table(bout_rows, seed=seed)
    if trial_keys is not None:
        allowed = {str(k) for k in trial_keys}
        search_keys = tuple(k for k in by_trial if k in allowed)
    else:
        search_keys = tuple(by_trial.keys())
    out: list[MinedSequence] = []
    for cand in candidates:
        speeds: list[float] = []
        dheads: list[float] = []
        straights: list[float] = []
        areas: list[float] = []
        durations: list[float] = []
        distances: list[float] = []
        iqr_speeds: list[float] = []
        headings: list[float] = []
        for tk in search_keys:
            for row in _pattern_match_bout_rows(cand.pattern, str(tk), by_trial):
                speed = float(row["bout_mean_speed_mps"])
                speeds.append(speed)
                dheads.append(float(row["bout_mean_abs_dheading"]))
                straights.append(float(row.get("bout_straightness", "0") or 0))
                areas.append(float(row["bout_mean_blob_area_px2"]))
                dur = _opt_float(row, "bout_duration_s")
                if dur is not None:
                    durations.append(dur)
                    if np.isfinite(speed):
                        distances.append(speed * dur)
                iqr = _opt_float(row, "bout_iqr_speed_mps")
                if iqr is not None:
                    iqr_speeds.append(iqr)
                heading = _opt_float(row, "bout_mean_heading_rad")
                if heading is not None:
                    headings.append(heading)
        if not speeds:
            out.append(cand)
            continue
        out.append(
            replace(
                cand,
                mean_speed_mps=float(np.nanmean(speeds)),
                mean_abs_dheading=float(np.nanmean(dheads)),
                mean_straightness=float(np.nanmean(straights)),
                mean_blob_area_px2=float(np.nanmean(areas)),
                mean_duration_s=float(np.nanmean(durations)) if durations else None,
                mean_distance_m=float(np.nanmean(distances)) if distances else None,
                mean_iqr_speed_mps=float(np.nanmean(iqr_speeds)) if iqr_speeds else None,
                mean_heading_rad=_circular_mean(headings),
            )
        )
    return out


def compute_must_review_overlay(
    cand: MinedSequence,
    bout_rows: Sequence[Mapping[str, str]],
    *,
    seed: str | None = None,
) -> bool:
    """True when exemplar overlay is required before naming."""
    by_trial = _trial_bout_table(bout_rows, seed=seed)
    for tk in cand.example_trial_keys or tuple(by_trial.keys()):
        for row in _pattern_match_bout_rows(cand.pattern, str(tk), by_trial):
            if str(row.get("ambiguous", "0")).strip() in {"1", "true", "True"}:
                return True
            iqr = float(row.get("bout_iqr_speed_mps", "0") or 0)
            if iqr > DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS:
                return True
    if cand.mean_speed_mps is not None:
        sp = float(cand.mean_speed_mps)
        if OVERLAY_SPEED_GRAY_LO_MPS <= sp <= OVERLAY_SPEED_GRAY_HI_MPS:
            return True
        if sp < OVERLAY_LOW_SPEED_MPS and cand.mean_abs_dheading is not None:
            if float(cand.mean_abs_dheading) >= OVERLAY_HIGH_DHEADING:
                return True
    return False


def flag_candidates_for_overlay_review(
    candidates: Sequence[MinedSequence],
    bout_rows: Sequence[Mapping[str, str]],
    *,
    seed: str | None = None,
) -> list[MinedSequence]:
    return [replace(cand, must_review_overlay=compute_must_review_overlay(cand, bout_rows, seed=seed)) for cand in candidates]


def validate_curated_candidate_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    force: bool = False,
) -> dict[str, str]:
    """Validate curated CSV; return behavior_name → anchor_bucket map."""
    errors: list[str] = []
    buckets: dict[str, str] = {}
    for i, row in enumerate(rows, start=2):
        name = str(row.get("behavior_name", "")).strip()
        if not name:
            continue
        bucket_raw = str(row.get("anchor_bucket", "")).strip()
        if not bucket_raw:
            errors.append(f"line {i}: behavior_name={name!r} missing anchor_bucket")
            continue
        try:
            bucket = normalize_anchor_bucket(bucket_raw)
        except ValueError as exc:
            errors.append(f"line {i}: {exc}")
            continue
        prev = buckets.get(name)
        if prev is not None and prev != bucket:
            errors.append(f"line {i}: behavior_name {name!r} has conflicting anchor_bucket " f"{bucket!r} vs {prev!r}")
        buckets[name] = bucket
        must_review = str(row.get("must_review_overlay", "0")).strip() in {"1", "true", "True"}
        reviewed = str(row.get("reviewed_at", "")).strip()
        if must_review and not reviewed and not force:
            pat = row.get("pattern_json", "")
            errors.append(f"line {i}: pattern {pat} requires overlay review (must_review_overlay=1) " "but reviewed_at is empty; use --force to override")
    if errors:
        raise ValueError("candidate curation validation failed:\n" + "\n".join(errors))
    if not buckets:
        raise ValueError("no curated rows with behavior_name and anchor_bucket")
    return buckets
