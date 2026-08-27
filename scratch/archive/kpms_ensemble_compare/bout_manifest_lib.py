"""Shared bout + prototype feature extraction for manifest long tables."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import keypoint_moseq as kpms
import numpy as np

from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.io.file_discovery import load_manifest_csv
from behavior_ethogram_phase_i import (
    DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
    extend_features_tmax,
    hdbscan_labels_path,
    load_hdbscan_label_table,
    prototype_scalars_from_bouts,
)
from movement_layer import load_ambulation_xy, movement_series_for_trial
from syllable_speed_cluster import (
    T_MAX,
    T_MIN,
    _curve_to_features,
    _decode_state,
    _iter_bouts,
    _pad_features,
    _phase_mask,
    _resample_bout,
)

PhaseKind = str

BOUT_LONG_FIELDS = (
    "stream",
    "seed",
    "animal_id",
    "session",
    "trial",
    "trial_key",
    "kpms_recording_key",
    "raw_syllable_id",
    "bout_index",
    "row_start",
    "row_end",
    "bout_frames",
    "bout_mean_speed_mps",
    "bout_mean_abs_dheading",
    "bout_frac_still",
    "bout_frac_run",
    "bout_primary_state",
    "prototype_T_s",
    "prototype_median_bout_frames",
    "prototype_max_bout_frames",
    "phase_scope",
)

PROTOTYPE_FEATURE_FIELDS_PREFIX = (
    "stream",
    "seed",
    "raw_syllable_id",
    "T_s",
    "T_max_seed",
    "T_max_stream",
    "n_pad_dims",
    "n_bouts",
    "median_bout_frames",
    "max_bout_frames",
    "mean_speed_mps",
    "mean_abs_dheading",
    "frac_still",
    "bout_speed_iqr",
    "ambiguous",
    "cluster_id",
)


@dataclass
class BoutLongRow:
    stream: str
    seed: str
    animal_id: str
    session: str
    trial: str
    trial_key: str
    kpms_recording_key: str
    raw_syllable_id: int
    bout_index: int
    row_start: int
    row_end: int
    bout_frames: int
    bout_mean_speed_mps: float
    bout_mean_abs_dheading: float
    bout_frac_still: float
    bout_frac_run: float
    bout_primary_state: str
    prototype_T_s: int
    prototype_median_bout_frames: float
    prototype_max_bout_frames: int
    phase_scope: str


@dataclass
class PrototypeFeatureRow:
    stream: str
    seed: str
    raw_syllable_id: int
    T_s: int
    T_max_seed: int
    T_max_stream: int
    n_pad_dims: int
    n_bouts: int
    median_bout_frames: float
    max_bout_frames: int
    mean_speed_mps: float
    mean_abs_dheading: float
    frac_still: float
    bout_speed_iqr: float
    ambiguous: bool
    cluster_id: int = -1
    features: np.ndarray = field(repr=False, default_factory=lambda: np.array([]))


def feature_column_names(t_max: int) -> list[str]:
    return [f"feat_{i:03d}" for i in range(3 * t_max)]


def prototype_csv_fieldnames(t_max: int) -> list[str]:
    return [*PROTOTYPE_FEATURE_FIELDS_PREFIX, *feature_column_names(t_max)]


def _primary_state(states: np.ndarray) -> str:
    if states.size == 0:
        return ""
    vals, counts = np.unique(states.astype(str), return_counts=True)
    return str(vals[int(np.argmax(counts))])


def collect_stream_tables(
    *,
    kpms_root: Path,
    legacy_db: Path,
    manifest_path: Path,
    stream: str,
    seeds: tuple[str, ...],
    phase: PhaseKind,
    min_bout_frames: int,
    tracking_h5: Path | None,
    ambiguous_threshold_mps: float = DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
    cluster_lookup: dict[tuple[str, str, int], int] | None = None,
) -> tuple[list[BoutLongRow], list[PrototypeFeatureRow], int]:
    manifests = {m.kpms_results_dict_key: m for m in load_manifest_csv(manifest_path)}
    track_db = tracking_h5 or (kpms_root / "kpms_tracking.h5")
    bout_rows: list[BoutLongRow] = []
    proto_by_key: dict[tuple[str, int], PrototypeFeatureRow] = {}
    bout_lengths: dict[tuple[str, int], list[int]] = defaultdict(list)
    bout_mean_speeds: dict[tuple[str, int], list[float]] = defaultdict(list)
    bout_curves: dict[tuple[str, int], list[np.ndarray]] = defaultdict(list)
    is_moving_frames: dict[tuple[str, int], list[bool]] = defaultdict(list)
    heading_frames: dict[tuple[str, int], list[float]] = defaultdict(list)
    speed_sums: dict[tuple[str, int], float] = defaultdict(float)
    speed_counts: dict[tuple[str, int], int] = defaultdict(int)
    bout_index_ctr: dict[tuple[str, str, int], int] = defaultdict(int)
    seed_t_max: dict[str, int] = {}

    for seed in seeds:
        results_path = kpms_root / stream / f"seed_{seed}" / "results_apply.h5"
        if not results_path.is_file():
            continue
        pre_cfg = KpmsPreprocessConfig(
            min_fragment_frames=4,
            jump_filter_cm=15.0,
            jump_filter_lookahead_frames=3,
            px_per_cm=2.42,
            retain_all_frames=False,
            db_path=track_db,
            pose_stream=stream,  # type: ignore[arg-type]
        )
        results = kpms.load_hdf5(str(results_path))

        for tkey, rec in results.items():
            manifest = manifests.get(tkey)
            if manifest is None:
                continue
            syll = np.asarray(rec["syllable"]).ravel()
            heading = np.asarray(rec.get("heading", np.zeros_like(syll))).ravel()
            mv = movement_series_for_trial(
                manifest,
                stream,  # type: ignore[arg-type]
                legacy_db,
                pre_cfg=pre_cfg,
            )
            if mv is None or mv.source_frames.shape[0] != syll.shape[0]:
                continue
            xy = load_ambulation_xy(legacy_db, manifest)
            if xy is None:
                continue
            fts = {int(row["frame_index"]): _decode_state(row["trial_state"]) for row in xy}
            states = np.array([fts.get(int(f), "") for f in mv.source_frames], dtype=object)
            mask = _phase_mask(states, phase)  # type: ignore[arg-type]

            for sid, sl in _iter_bouts(syll, mask, min_bout_frames=min_bout_frames):
                key = (seed, int(sid))
                bout_lengths[key].append(int(sl.stop - sl.start))

        t_by_syll: dict[tuple[str, int], int] = {}
        for key, lengths in bout_lengths.items():
            if key[0] != seed or not lengths:
                continue
            med = float(np.median(lengths))
            t_by_syll[key] = int(np.clip(round(1.5 * med), T_MIN, T_MAX))
        if not t_by_syll:
            continue
        seed_t_max[seed] = int(max(t_by_syll.values()))

        for tkey, rec in results.items():
            manifest = manifests.get(tkey)
            if manifest is None:
                continue
            syll = np.asarray(rec["syllable"]).ravel()
            heading = np.asarray(rec.get("heading", np.zeros_like(syll))).ravel()
            mv = movement_series_for_trial(
                manifest,
                stream,  # type: ignore[arg-type]
                legacy_db,
                pre_cfg=pre_cfg,
            )
            if mv is None or mv.source_frames.shape[0] != syll.shape[0]:
                continue
            xy = load_ambulation_xy(legacy_db, manifest)
            if xy is None:
                continue
            fts = {int(row["frame_index"]): _decode_state(row["trial_state"]) for row in xy}
            states = np.array([fts.get(int(f), "") for f in mv.source_frames], dtype=object)
            mask = _phase_mask(states, phase)  # type: ignore[arg-type]

            for sid, sl in _iter_bouts(syll, mask, min_bout_frames=min_bout_frames):
                seed_key = (seed, int(sid))
                if seed_key not in t_by_syll:
                    continue
                spd = mv.speed_mps[sl]
                hd = heading[sl]
                still = mv.is_moving[sl]
                state_sl = states[sl]
                if hd.size >= 2:
                    dh = float(np.mean(np.abs(np.diff(np.unwrap(hd.astype(np.float64))))))
                else:
                    dh = 0.0
                bout_idx_key = (seed, manifest.trial_key, int(sid))
                bout_index_ctr[bout_idx_key] += 1
                lengths = bout_lengths[seed_key]
                med_len = float(np.median(lengths)) if lengths else float(sl.stop - sl.start)
                bout_rows.append(
                    BoutLongRow(
                        stream=stream,
                        seed=seed,
                        animal_id=manifest.animal_id,
                        session=manifest.session,
                        trial=manifest.trial,
                        trial_key=manifest.trial_key,
                        kpms_recording_key=manifest.kpms_results_dict_key,
                        raw_syllable_id=int(sid),
                        bout_index=bout_index_ctr[bout_idx_key],
                        row_start=int(sl.start),
                        row_end=int(sl.stop),
                        bout_frames=int(sl.stop - sl.start),
                        bout_mean_speed_mps=float(np.mean(spd)),
                        bout_mean_abs_dheading=dh,
                        bout_frac_still=float(np.mean(~still.astype(bool))),
                        bout_frac_run=float(np.mean(state_sl == "run")),
                        bout_primary_state=_primary_state(state_sl),
                        prototype_T_s=t_by_syll[seed_key],
                        prototype_median_bout_frames=med_len,
                        prototype_max_bout_frames=int(max(lengths)) if lengths else int(sl.stop - sl.start),
                        phase_scope=phase,
                    )
                )
                bout_mean_speeds[seed_key].append(float(np.mean(spd)))
                is_moving_frames[seed_key].extend(bool(x) for x in still)
                heading_frames[seed_key].extend(float(x) for x in hd if np.isfinite(x))
                speed_sums[seed_key] += float(np.sum(spd))
                speed_counts[seed_key] += int(spd.size)
                t_s = t_by_syll[seed_key]
                sp, hd_rs = _resample_bout(spd, hd, n_points=t_s)
                bout_curves[seed_key].append(_curve_to_features(sp, hd_rs))

        for (seed_key, t_s) in t_by_syll.items():
            seed, raw_id = seed_key
            curves = bout_curves.get(seed_key, [])
            if not curves:
                continue
            med_curve = np.median(np.stack(curves, axis=0), axis=0)
            t_max_seed = seed_t_max[seed]
            feat = _pad_features(med_curve, t_s=t_s, t_max=t_max_seed)
            scalars = prototype_scalars_from_bouts(
                is_moving_frames=np.asarray(is_moving_frames.get(seed_key, []), dtype=bool),
                heading_frames=np.asarray(heading_frames.get(seed_key, []), dtype=np.float64),
                bout_mean_speeds=bout_mean_speeds.get(seed_key, []),
                ambiguous_threshold_mps=ambiguous_threshold_mps,
            )
            lengths = bout_lengths[seed_key]
            cid = -1
            if cluster_lookup is not None:
                cid = cluster_lookup.get((stream, seed, raw_id), -1)
            proto_by_key[seed_key] = PrototypeFeatureRow(
                stream=stream,
                seed=seed,
                raw_syllable_id=raw_id,
                T_s=t_s,
                T_max_seed=t_max_seed,
                T_max_stream=t_max_seed,
                n_pad_dims=3 * (t_max_seed - t_s),
                n_bouts=len(curves),
                median_bout_frames=float(np.median(lengths)),
                max_bout_frames=int(max(lengths)),
                mean_speed_mps=speed_sums[seed_key] / max(speed_counts[seed_key], 1),
                mean_abs_dheading=scalars.mean_abs_dheading,
                frac_still=scalars.frac_still,
                bout_speed_iqr=scalars.bout_speed_iqr,
                ambiguous=scalars.ambiguous,
                cluster_id=cid,
                features=feat,
            )

    if not proto_by_key:
        return bout_rows, [], 0

    stream_t_max = max(p.T_max_seed for p in proto_by_key.values())
    for _key, proto in proto_by_key.items():
        if proto.T_max_seed == stream_t_max:
            aligned = proto.features.copy()
        else:
            aligned = extend_features_tmax(
                proto.features,
                t_s=proto.T_s,
                t_max_from=proto.T_max_seed,
                t_max_to=stream_t_max,
            )
        proto.T_max_stream = stream_t_max
        proto.n_pad_dims = 3 * (stream_t_max - proto.T_s)
        proto.features = aligned

    proto_rows = [proto_by_key[k] for k in sorted(proto_by_key.keys(), key=lambda x: (x[0], x[1]))]
    return bout_rows, proto_rows, stream_t_max


def load_cluster_lookup(phase_i_dir: Path, stream: str, phase: str) -> dict[tuple[str, str, int], int]:
    path = hdbscan_labels_path(phase_i_dir, stream, phase=phase)
    if not path.is_file():
        return {}
    table = load_hdbscan_label_table(path)
    return {(stream, seed, raw_id): st.cluster_id for (seed, raw_id), st in table.items()}


def bout_row_to_dict(row: BoutLongRow) -> dict[str, object]:
    return {
        "stream": row.stream,
        "seed": row.seed,
        "animal_id": row.animal_id,
        "session": row.session,
        "trial": row.trial,
        "trial_key": row.trial_key,
        "kpms_recording_key": row.kpms_recording_key,
        "raw_syllable_id": row.raw_syllable_id,
        "bout_index": row.bout_index,
        "row_start": row.row_start,
        "row_end": row.row_end,
        "bout_frames": row.bout_frames,
        "bout_mean_speed_mps": round(row.bout_mean_speed_mps, 6),
        "bout_mean_abs_dheading": round(row.bout_mean_abs_dheading, 6),
        "bout_frac_still": round(row.bout_frac_still, 6),
        "bout_frac_run": round(row.bout_frac_run, 6),
        "bout_primary_state": row.bout_primary_state,
        "prototype_T_s": row.prototype_T_s,
        "prototype_median_bout_frames": round(row.prototype_median_bout_frames, 3),
        "prototype_max_bout_frames": row.prototype_max_bout_frames,
        "phase_scope": row.phase_scope,
    }


def prototype_row_to_dict(row: PrototypeFeatureRow, *, t_max: int) -> dict[str, object]:
    out: dict[str, object] = {
        "stream": row.stream,
        "seed": row.seed,
        "raw_syllable_id": row.raw_syllable_id,
        "T_s": row.T_s,
        "T_max_seed": row.T_max_seed,
        "T_max_stream": row.T_max_stream,
        "n_pad_dims": row.n_pad_dims,
        "n_bouts": row.n_bouts,
        "median_bout_frames": round(row.median_bout_frames, 3),
        "max_bout_frames": row.max_bout_frames,
        "mean_speed_mps": round(row.mean_speed_mps, 6),
        "mean_abs_dheading": round(row.mean_abs_dheading, 6),
        "frac_still": round(row.frac_still, 6),
        "bout_speed_iqr": round(row.bout_speed_iqr, 6),
        "ambiguous": int(row.ambiguous),
        "cluster_id": row.cluster_id,
    }
    for i, name in enumerate(feature_column_names(t_max)):
        val = float(row.features[i]) if i < row.features.size else ""
        out[name] = round(val, 6) if val != "" else ""
    return out
