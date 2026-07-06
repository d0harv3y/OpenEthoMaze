"""Bout exemplar selection for behavior-token grid review."""

from __future__ import annotations

import math
from typing import Mapping, Sequence

import numpy as np

from .grammar_matches import DEFAULT_PREVIEW_PADDING_S, PatternMatch, clip_frames_for_match

DEFAULT_MAX_TOKEN_EXEMPLARS = 10


def pattern_match_from_bout_row(
    trial_key: str,
    row: Mapping[str, str],
    source_frame_index: Sequence[int] | np.ndarray,
) -> PatternMatch | None:
    """Build a single-bout :class:`PatternMatch` with source-video frame bounds."""
    src = np.asarray(source_frame_index, dtype=np.int64).ravel()
    row_start = int(row["row_start"])
    row_end = int(row["row_end_exclusive"])
    bout_index = int(row["bout_index"])
    if row_start < 0 or row_end <= row_start or row_start >= len(src):
        return None
    hi = min(row_end, len(src))
    return PatternMatch(
        trial_key=str(trial_key),
        bout_start_index=bout_index,
        bout_end_exclusive=bout_index + 1,
        row_start=row_start,
        row_end_exclusive=row_end,
        source_start_frame=int(src[row_start]),
        source_end_frame=int(src[hi - 1]),
    )


def _bout_ambiguous(row: Mapping[str, str]) -> bool:
    return str(row.get("ambiguous", "0")).strip() in {"1", "true", "True"}


def _token_mean_speed(rows: Sequence[Mapping[str, str]]) -> float | None:
    speeds = [float(r["bout_mean_speed_mps"]) for r in rows]
    if not speeds:
        return None
    arr = np.asarray(speeds, dtype=np.float64)
    if arr.size == 0 or not np.any(np.isfinite(arr)):
        return None
    mean = float(np.nanmean(arr))
    return mean if math.isfinite(mean) else None


def overlay_clip_fits_usable_frames(
    match: PatternMatch,
    *,
    fps: float,
    padding_s: float,
    usable_frame_end_exclusive: int,
) -> bool:
    """True when padded bout clip fits unified-overlay source video bounds."""
    clip_start, clip_end = clip_frames_for_match(match, fps=fps, padding_s=padding_s)
    end_exclusive = int(usable_frame_end_exclusive)
    if int(clip_start) >= end_exclusive:
        return False
    run_len = end_exclusive - int(clip_start)
    run_len = min(run_len, int(clip_end) - int(clip_start) + 1)
    return run_len > 0


def _candidate_sort_key(
    *,
    ambiguous: bool,
    mean_speed: float,
    token_mean_speed: float | None,
    trial_key: str,
) -> tuple[int, float, str]:
    amb_rank = 1 if ambiguous else 0
    if token_mean_speed is not None and math.isfinite(mean_speed) and math.isfinite(token_mean_speed):
        speed_rank = abs(mean_speed - float(token_mean_speed))
    else:
        speed_rank = 0.0
    return (amb_rank, speed_rank, trial_key)


def select_token_bout_exemplars(
    bout_rows: Sequence[Mapping[str, str]],
    *,
    behavior_token: int,
    trial_source_frames: Mapping[str, Sequence[int] | np.ndarray],
    seed: str | None = None,
    max_exemplars: int = DEFAULT_MAX_TOKEN_EXEMPLARS,
    padding_s: float = DEFAULT_PREVIEW_PADDING_S,
    trial_fps: Mapping[str, float] | None = None,
    trial_usable_overlay_frame_end: Mapping[str, int] | None = None,
    require_overlay_clip_fit: bool = False,
) -> tuple[PatternMatch, ...]:
    """Pick diverse, review-friendly bout spans for one ``behavior_token``."""
    if max_exemplars < 1:
        return ()

    token_rows = [row for row in bout_rows if str(row.get("behavior_token", "")).strip() == str(int(behavior_token)) and (seed is None or str(row.get("seed", "")) == str(seed))]
    token_mean_speed = _token_mean_speed(token_rows)

    candidates: list[tuple[PatternMatch, bool, float]] = []
    for row in token_rows:
        trial_key = str(row["trial_key"])
        src = trial_source_frames.get(trial_key)
        if src is None:
            continue
        match = pattern_match_from_bout_row(trial_key, row, src)
        if match is None:
            continue
        if require_overlay_clip_fit:
            end_exclusive = (
                int(trial_usable_overlay_frame_end[trial_key])
                if trial_usable_overlay_frame_end is not None
                else None
            )
            fps = float(trial_fps[trial_key]) if trial_fps is not None else None
            if end_exclusive is None or fps is None or fps <= 0:
                continue
            if not overlay_clip_fits_usable_frames(
                match,
                fps=fps,
                padding_s=padding_s,
                usable_frame_end_exclusive=end_exclusive,
            ):
                continue
        candidates.append(
            (
                match,
                _bout_ambiguous(row),
                float(row["bout_mean_speed_mps"]),
            )
        )

    candidates.sort(
        key=lambda t: _candidate_sort_key(
            ambiguous=t[1],
            mean_speed=t[2],
            token_mean_speed=token_mean_speed,
            trial_key=t[0].trial_key,
        )
    )

    seen_trials: set[str] = set()
    picked: list[PatternMatch] = []
    for match, _amb, _sp in candidates:
        if match.trial_key in seen_trials:
            continue
        picked.append(match)
        seen_trials.add(match.trial_key)
        if len(picked) >= max_exemplars:
            break
    if len(picked) < max_exemplars:
        for match, _amb, _sp in candidates:
            if match in picked:
                continue
            picked.append(match)
            if len(picked) >= max_exemplars:
                break
    return tuple(picked)


def unique_behavior_tokens(
    bout_rows: Sequence[Mapping[str, str]],
    *,
    seed: str | None = None,
) -> tuple[int, ...]:
    """Sorted token ids present in the bout table."""
    tokens: set[int] = set()
    for row in bout_rows:
        if seed is not None and str(row.get("seed", "")) != str(seed):
            continue
        raw = str(row.get("behavior_token", "")).strip()
        if not raw:
            continue
        tokens.add(int(raw))
    return tuple(sorted(tokens))
