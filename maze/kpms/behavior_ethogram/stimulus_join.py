"""Join per-frame VAST stimulus signals onto kpMS syllable bouts."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import h5py
import numpy as np

from maze.core.h5_layout import read_feedback_table, resolve_ambulation_metrics_group
from maze.core.schema import XY_ROW_DTYPE
from maze.kpms.frame_alignment import KpmsAlignmentCache, kpms_recording_key
from maze.kpms.h5_pose import resolve_canonical_trial_h5
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.db.trial_key import TrialKey, resolve_trial_key_for_hdf5
from maze.pipeline.io.file_discovery import TrialManifest

from .behavior_token_summarize import bout_in_phase
from .stimulus_join_contract import (
    ALLOWED_GENOTYPE_STRAINS,
    STIMULUS_BOUT_TABLE_FIELDS,
)

_XY_POINT_PRIORITY: tuple[str, ...] = ("spot_hybrid", "spot", "center", "centroid")


@dataclass(frozen=True)
class StimulusJoinFilterConfig:
    """Cohort filters for stimulus/bout join (defaults match pilot plan)."""

    experiments: tuple[str, ...] = ("VASTcont", "VASTalt")
    drop_strains: tuple[str, ...] = ("?", "")
    drop_blank_sex: bool = True
    tx_values: tuple[str, ...] | None = None
    allowed_strains: frozenset[str] = ALLOWED_GENOTYPE_STRAINS


@dataclass(frozen=True)
class TrialStimulusFrames:
    """Per source-video-frame stimulus scalars for one trial."""

    motor_fb: np.ndarray
    dist_to_exit_px: np.ndarray


@dataclass(frozen=True)
class StimulusH5Verification:
    """Result of checking one trial H5 for stimulus join prerequisites."""

    trial_key: str
    h5_path: str
    has_feedback_table: bool
    has_motor_fb: bool
    has_xy_dist: bool
    n_feedback_frames: int
    n_xy_frames: int
    motor_fb_finite_frac: float
    dist_finite_frac: float

    @property
    def ok(self) -> bool:
        return (
            self.has_feedback_table
            and self.has_motor_fb
            and self.has_xy_dist
            and self.n_feedback_frames > 0
            and self.n_xy_frames > 0
            and self.motor_fb_finite_frac > 0.0
            and self.dist_finite_frac > 0.0
        )


def _normalize_label(value: object) -> str:
    return str(value or "").strip()


def _strain_allowed(strain: str, cfg: StimulusJoinFilterConfig) -> bool:
    s = _normalize_label(strain)
    if s in cfg.drop_strains:
        return False
    if s not in cfg.allowed_strains:
        raise ValueError(
            f"unmapped strain {strain!r}; allowed after drop filter: {sorted(cfg.allowed_strains)}"
        )
    return True


def filter_bout_rows(rows: Sequence[Mapping[str, str]], cfg: StimulusJoinFilterConfig) -> list[dict[str, str]]:
    """Apply experiment / strain / sex / tx filters to bout table rows."""
    out: list[dict[str, str]] = []
    for row in rows:
        experiment = _normalize_label(row.get("experiment", ""))
        if cfg.experiments and experiment not in cfg.experiments:
            continue
        strain = _normalize_label(row.get("strain", ""))
        if strain in cfg.drop_strains:
            continue
        if not _strain_allowed(strain, cfg):
            continue
        sex = _normalize_label(row.get("sex", ""))
        if cfg.drop_blank_sex and not sex:
            continue
        tx = _normalize_label(row.get("tx", ""))
        if cfg.tx_values is not None and tx not in cfg.tx_values:
            continue
        out.append(dict(row))
    return out


def _resolve_trial_group(h5: h5py.File, trial_key: TrialKey) -> h5py.Group | None:
    resolved = resolve_trial_key_for_hdf5(h5, trial_key)
    group_path = resolved.path().lstrip("/")
    if group_path not in h5:
        return None
    return h5[group_path]


def _read_xy_dist_to_exit(g_trial: h5py.Group) -> np.ndarray | None:
    g_amb = resolve_ambulation_metrics_group(g_trial)
    if g_amb is None:
        return None
    for point in _XY_POINT_PRIORITY:
        if point not in g_amb:
            continue
        g_pt = g_amb[point]
        if "xy" not in g_pt:
            continue
        rec = g_pt["xy"][:]
        if rec.dtype != XY_ROW_DTYPE or "dist_to_exit_px" not in rec.dtype.names:
            continue
        return np.asarray(rec["dist_to_exit_px"], dtype=np.float64)
    return None


def read_trial_stimulus_frames(g_trial: h5py.Group) -> TrialStimulusFrames | None:
    """Read per-frame motor duty and distance-to-exit from a trial HDF5 group."""
    fb_table = read_feedback_table(g_trial)
    if fb_table is None or "motor_fb" not in fb_table.dtype.names:
        return None
    motor_fb = np.asarray(fb_table["motor_fb"], dtype=np.float64)
    dist = _read_xy_dist_to_exit(g_trial)
    if dist is None:
        return None
    n = min(len(motor_fb), len(dist))
    if n == 0:
        return None
    return TrialStimulusFrames(motor_fb=motor_fb[:n], dist_to_exit_px=dist[:n])


def read_trial_stimulus_frames_from_path(h5_path: Path | str, trial_key: TrialKey) -> TrialStimulusFrames | None:
    path = Path(h5_path)
    if not path.is_file():
        return None
    with h5py.File(path, "r") as h5:
        g_trial = _resolve_trial_group(h5, trial_key)
        if g_trial is None:
            return None
        return read_trial_stimulus_frames(g_trial)


def verify_trial_stimulus_h5(h5_path: Path | str, trial_key: TrialKey) -> StimulusH5Verification:
    """Check whether a trial H5 has populated stimulus paths for join."""
    path = Path(h5_path)
    key_str = trial_key.path().lstrip("/")
    if not path.is_file():
        return StimulusH5Verification(
            trial_key=key_str,
            h5_path=str(path),
            has_feedback_table=False,
            has_motor_fb=False,
            has_xy_dist=False,
            n_feedback_frames=0,
            n_xy_frames=0,
            motor_fb_finite_frac=0.0,
            dist_finite_frac=0.0,
        )
    with h5py.File(path, "r") as h5:
        g_trial = _resolve_trial_group(h5, trial_key)
        if g_trial is None:
            return StimulusH5Verification(
                trial_key=key_str,
                h5_path=str(path),
                has_feedback_table=False,
                has_motor_fb=False,
                has_xy_dist=False,
                n_feedback_frames=0,
                n_xy_frames=0,
                motor_fb_finite_frac=0.0,
                dist_finite_frac=0.0,
            )
        fb_table = read_feedback_table(g_trial)
        has_fb = fb_table is not None
        motor = np.asarray(fb_table["motor_fb"], dtype=np.float64) if has_fb else np.array([], dtype=np.float64)
        dist = _read_xy_dist_to_exit(g_trial)
        has_dist = dist is not None
        dist_arr = dist if dist is not None else np.array([], dtype=np.float64)
        motor_frac = float(np.isfinite(motor).mean()) if motor.size else 0.0
        dist_frac = float(np.isfinite(dist_arr).mean()) if dist_arr.size else 0.0
        return StimulusH5Verification(
            trial_key=key_str,
            h5_path=str(path.resolve()),
            has_feedback_table=has_fb,
            has_motor_fb=has_fb and motor.size > 0,
            has_xy_dist=has_dist and dist_arr.size > 0,
            n_feedback_frames=int(motor.size),
            n_xy_frames=int(dist_arr.size),
            motor_fb_finite_frac=motor_frac,
            dist_finite_frac=dist_frac,
        )


def mean_scalar_over_rows(
    values: np.ndarray,
    source_frame_indices: np.ndarray,
    row_start: int,
    row_end_exclusive: int,
) -> float:
    """Mean ``values`` at source frames covered by kpMS row span ``[row_start, row_end_exclusive)``."""
    src = np.asarray(source_frame_indices, dtype=np.int64).ravel()
    vals = np.asarray(values, dtype=np.float64).ravel()
    if row_end_exclusive <= row_start:
        return float("nan")
    frame_idx = src[row_start:row_end_exclusive]
    in_range = (frame_idx >= 0) & (frame_idx < len(vals))
    if not np.any(in_range):
        return float("nan")
    picked = vals[frame_idx[in_range]]
    finite = picked[np.isfinite(picked)]
    if finite.size == 0:
        return float("nan")
    return float(np.mean(finite))


def enrich_bout_row_with_stimulus(
    row: Mapping[str, str],
    *,
    stimulus: TrialStimulusFrames,
    source_frame_indices: np.ndarray,
) -> dict[str, str]:
    """Add ``bout_mean_duty`` and ``bout_mean_dist_px`` to one bout row."""
    row_start = int(row["row_start"])
    row_end = int(row["row_end_exclusive"])
    out = dict(row)
    out["bout_mean_duty"] = mean_scalar_over_rows(stimulus.motor_fb, source_frame_indices, row_start, row_end)
    out["bout_mean_dist_px"] = mean_scalar_over_rows(
        stimulus.dist_to_exit_px, source_frame_indices, row_start, row_end
    )
    return out


def _manifest_for_trial_key(
    manifests_by_key: Mapping[str, TrialManifest],
    trial_key: str,
) -> TrialManifest | None:
    if trial_key in manifests_by_key:
        return manifests_by_key[trial_key]
    for manifest in manifests_by_key.values():
        if kpms_recording_key(manifest) == trial_key:
            return manifest
    return None


@dataclass(frozen=True)
class StimulusJoinStats:
    n_input_rows: int
    n_output_rows: int
    n_trials_seen: int
    n_trials_joined: int
    n_trials_skipped_no_manifest: int
    n_trials_skipped_no_alignment: int
    n_trials_skipped_no_stimulus: int


def join_stimulus_to_bouts(
    bout_rows: Sequence[Mapping[str, str]],
    manifests: Sequence[TrialManifest],
    *,
    pre_cfg: KpmsPreprocessConfig,
    alignment_cache: KpmsAlignmentCache,
    stimulus_h5: Path | None = None,
) -> tuple[list[dict[str, str]], StimulusJoinStats]:
    """Enrich filtered bout rows with per-bout stimulus means."""
    manifests_by_key = {kpms_recording_key(m): m for m in manifests}
    rows_by_trial: dict[str, list[Mapping[str, str]]] = {}
    for row in bout_rows:
        rows_by_trial.setdefault(str(row["trial_key"]), []).append(row)

    enriched: list[dict[str, str]] = []
    n_skipped_manifest = 0
    n_skipped_alignment = 0
    n_skipped_stimulus = 0
    n_joined = 0
    db_path = pre_cfg.db_path if pre_cfg.db_path is not None else Path()
    for trial_key, trial_rows in sorted(rows_by_trial.items()):
        manifest = _manifest_for_trial_key(manifests_by_key, trial_key)
        if manifest is None:
            n_skipped_manifest += 1
            continue
        aligned = alignment_cache.aligned_trial(manifest, pre_cfg)
        if aligned is None:
            n_skipped_alignment += 1
            continue
        h5_path = stimulus_h5
        if h5_path is None:
            resolved = resolve_canonical_trial_h5(manifest, db_path)
            if resolved is None:
                n_skipped_stimulus += 1
                continue
            h5_path = resolved
        trial_key_obj = TrialKey.from_manifest(manifest)
        stimulus = read_trial_stimulus_frames_from_path(h5_path, trial_key_obj)
        if stimulus is None:
            n_skipped_stimulus += 1
            continue
        n_joined += 1
        src = aligned.source_frame_indices
        for row in trial_rows:
            out = enrich_bout_row_with_stimulus(row, stimulus=stimulus, source_frame_indices=src)
            for field in STIMULUS_BOUT_TABLE_FIELDS:
                if field in ("bout_mean_duty", "bout_mean_dist_px"):
                    out[field] = "" if not np.isfinite(float(out[field])) else f"{float(out[field]):.8g}"
                elif field not in out:
                    out[field] = str(row.get(field, ""))
            enriched.append({k: str(out.get(k, "")) for k in STIMULUS_BOUT_TABLE_FIELDS})
    stats = StimulusJoinStats(
        n_input_rows=len(bout_rows),
        n_output_rows=len(enriched),
        n_trials_seen=len(rows_by_trial),
        n_trials_joined=n_joined,
        n_trials_skipped_no_manifest=n_skipped_manifest,
        n_trials_skipped_no_alignment=n_skipped_alignment,
        n_trials_skipped_no_stimulus=n_skipped_stimulus,
    )
    return enriched, stats


def write_stimulus_bout_table_csv(path: Path | str, rows: Sequence[Mapping[str, object]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(STIMULUS_BOUT_TABLE_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_stimulus_bout_table_csv(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def bout_rows_for_phase(rows: Sequence[Mapping[str, str]], phase: str) -> list[dict[str, str]]:
    """Filter bout rows to ``run`` or ``iti`` phase (iti = non-run primary state)."""
    return [dict(r) for r in rows if bout_in_phase(str(r.get("bout_primary_state", "")), phase)]  # type: ignore[arg-type]
