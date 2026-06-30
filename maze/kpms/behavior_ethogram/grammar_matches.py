"""Pattern-match exemplars for grammar candidate review (S3.2)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from .grammar_enrich import _trial_bout_table
from .grammar_mine import MinedSequence

DEFAULT_MAX_EXAMPLE_MATCHES = 3
DEFAULT_PREVIEW_PADDING_S = 1.0


@dataclass(frozen=True)
class PatternMatch:
    """One bout-span occurrence of a candidate pattern in a trial."""

    trial_key: str
    bout_start_index: int
    bout_end_exclusive: int
    row_start: int
    row_end_exclusive: int
    source_start_frame: int
    source_end_frame: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> PatternMatch:
        return cls(
            trial_key=str(raw["trial_key"]),
            bout_start_index=int(raw["bout_start_index"]),
            bout_end_exclusive=int(raw["bout_end_exclusive"]),
            row_start=int(raw["row_start"]),
            row_end_exclusive=int(raw["row_end_exclusive"]),
            source_start_frame=int(raw["source_start_frame"]),
            source_end_frame=int(raw["source_end_frame"]),
        )


def _match_span_rows(
    pattern: tuple[int, ...],
    trial_key: str,
    by_trial: Mapping[str, list[tuple[int, Mapping[str, str]]]],
) -> list[tuple[int, int, list[Mapping[str, str]]]]:
    """Return ``(bout_start_index, bout_end_exclusive, bout_rows)`` for each match start."""
    items = by_trial.get(trial_key, [])
    if not items:
        return []
    bout_ids = [int(r["raw_syllable_id"]) for _i, r in items]
    n = len(pattern)
    spans: list[tuple[int, int, list[Mapping[str, str]]]] = []
    for start in range(len(bout_ids) - n + 1):
        if tuple(bout_ids[start : start + n]) != pattern:
            continue
        bout_rows = [items[start + j][1] for j in range(n)]
        bout_start = int(items[start][0])
        bout_end = int(items[start + n - 1][0]) + 1
        spans.append((bout_start, bout_end, bout_rows))
    return spans


def _span_ambiguous(bout_rows: Sequence[Mapping[str, str]]) -> bool:
    for row in bout_rows:
        if str(row.get("ambiguous", "0")).strip() in {"1", "true", "True"}:
            return True
    return False


def _span_mean_speed(bout_rows: Sequence[Mapping[str, str]]) -> float:
    speeds = [float(r["bout_mean_speed_mps"]) for r in bout_rows]
    return float(np.nanmean(speeds)) if speeds else float("nan")


def find_pattern_matches_in_trial(
    pattern: tuple[int, ...],
    trial_key: str,
    by_trial: Mapping[str, list[tuple[int, Mapping[str, str]]]],
    source_frame_index: Sequence[int] | np.ndarray,
) -> list[PatternMatch]:
    """Locate all pattern spans in one trial with source-video frame bounds."""
    src = np.asarray(source_frame_index, dtype=np.int64).ravel()
    out: list[PatternMatch] = []
    for bout_start, bout_end, bout_rows in _match_span_rows(pattern, trial_key, by_trial):
        row_start = int(bout_rows[0]["row_start"])
        row_end = int(bout_rows[-1]["row_end_exclusive"])
        if row_start < 0 or row_end <= row_start or row_start >= len(src):
            continue
        hi = min(row_end, len(src))
        source_start = int(src[row_start])
        source_end = int(src[hi - 1])
        out.append(
            PatternMatch(
                trial_key=str(trial_key),
                bout_start_index=bout_start,
                bout_end_exclusive=bout_end,
                row_start=row_start,
                row_end_exclusive=row_end,
                source_start_frame=source_start,
                source_end_frame=source_end,
            )
        )
    return out


def _match_sort_key(
    match: PatternMatch,
    *,
    ambiguous: bool,
    mean_speed: float,
    pattern_mean_speed: float | None,
) -> tuple[int, float, str]:
    amb_rank = 1 if ambiguous else 0
    if pattern_mean_speed is not None and np.isfinite(mean_speed) and np.isfinite(pattern_mean_speed):
        speed_rank = abs(mean_speed - float(pattern_mean_speed))
    else:
        speed_rank = 0.0
    return (amb_rank, speed_rank, match.trial_key)


def select_example_matches(
    pattern: tuple[int, ...],
    trial_keys: Sequence[str],
    by_trial: Mapping[str, list[tuple[int, Mapping[str, str]]]],
    trial_source_frames: Mapping[str, Sequence[int] | np.ndarray],
    *,
    max_matches: int = DEFAULT_MAX_EXAMPLE_MATCHES,
    pattern_mean_speed: float | None = None,
) -> tuple[PatternMatch, ...]:
    """Pick diverse, review-friendly exemplar spans across trials."""
    if max_matches < 1:
        return ()
    candidates: list[tuple[PatternMatch, bool, float]] = []
    for tk in trial_keys:
        src = trial_source_frames.get(str(tk))
        if src is None:
            continue
        for match in find_pattern_matches_in_trial(pattern, str(tk), by_trial, src):
            spans = _match_span_rows(pattern, str(tk), by_trial)
            bout_rows: list[Mapping[str, str]] = []
            for bs, be, rows in spans:
                if bs == match.bout_start_index and be == match.bout_end_exclusive:
                    bout_rows = list(rows)
                    break
            ambiguous = _span_ambiguous(bout_rows)
            mean_speed = _span_mean_speed(bout_rows)
            candidates.append((match, ambiguous, mean_speed))

    candidates.sort(
        key=lambda t: _match_sort_key(
            t[0],
            ambiguous=t[1],
            mean_speed=t[2],
            pattern_mean_speed=pattern_mean_speed,
        )
    )
    seen_trials: set[str] = set()
    picked: list[PatternMatch] = []
    for match, _amb, _sp in candidates:
        if match.trial_key in seen_trials:
            continue
        picked.append(match)
        seen_trials.add(match.trial_key)
        if len(picked) >= max_matches:
            break
    if len(picked) < max_matches:
        for match, _amb, _sp in candidates:
            if match in picked:
                continue
            picked.append(match)
            if len(picked) >= max_matches:
                break
    return tuple(picked)


def attach_example_matches_to_candidates(
    candidates: Sequence[MinedSequence],
    bout_rows: Sequence[Mapping[str, str]],
    trial_source_frames: Mapping[str, Sequence[int] | np.ndarray],
    *,
    seed: str | None = None,
    max_matches: int = DEFAULT_MAX_EXAMPLE_MATCHES,
) -> list[MinedSequence]:
    """Populate ``example_matches_json`` on each candidate from bout table + alignment."""
    from dataclasses import replace

    by_trial = _trial_bout_table(bout_rows, seed=seed)
    out: list[MinedSequence] = []
    for cand in candidates:
        keys = cand.example_trial_keys or tuple(sorted(by_trial.keys()))
        matches = select_example_matches(
            cand.pattern,
            keys,
            by_trial,
            trial_source_frames,
            max_matches=max_matches,
            pattern_mean_speed=cand.mean_speed_mps,
        )
        out.append(replace(cand, example_matches_json=example_matches_to_json(matches)))
    return out


def example_matches_to_json(matches: Sequence[PatternMatch]) -> str:
    return json.dumps([m.to_dict() for m in matches])


def parse_example_matches_json(raw: str) -> tuple[PatternMatch, ...]:
    text = str(raw).strip()
    if not text:
        return ()
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("example_matches_json must be a JSON list")
    return tuple(PatternMatch.from_dict(item) for item in parsed)


def clip_frames_for_match(
    match: PatternMatch,
    *,
    fps: float,
    padding_s: float = DEFAULT_PREVIEW_PADDING_S,
) -> tuple[int, int]:
    """Return ``(clip_source_start_frame, clip_source_end_frame)`` with padding."""
    pad = max(0, int(round(float(padding_s) * float(fps))))
    start = max(0, int(match.source_start_frame) - pad)
    end = int(match.source_end_frame) + pad
    if end < start:
        end = start
    return start, end


def manifest_lookup_by_kpms_key(manifest_path) -> dict[str, Any]:
    """Build ``kpms_recording_key`` → manifest map."""
    from maze.kpms.frame_alignment import kpms_recording_key
    from maze.pipeline.io.file_discovery import load_manifest_csv

    manifests = load_manifest_csv(manifest_path)
    return {kpms_recording_key(m): m for m in manifests}


def resolve_manifest_for_trial_key(manifest_path, trial_key: str):
    """Resolve a kpMS recording key to its manifest row."""
    by_key = manifest_lookup_by_kpms_key(manifest_path)
    manifest = by_key.get(str(trial_key))
    if manifest is None:
        raise KeyError(f"trial_key {trial_key!r} not found in manifest {manifest_path}")
    return manifest
