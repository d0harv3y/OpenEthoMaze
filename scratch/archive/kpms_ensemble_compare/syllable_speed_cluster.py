#!/usr/bin/env python3
"""Syllable speed rank + HDBSCAN clustering on bout kinematics (scratch).

Per-model (default) or per-stream (``--scope per-stream``) clustering. See grill-me
spec (2026-06): bout curves (speed + heading), HDBSCAN on z-scored features,
optional speed-ranked ethogram remap via ``speed_rank_table.csv``.

**PADDING EXPERIMENT (squishware):** After per-syllable adaptive resampling to
``T_s = clip(round(1.5 * median_bout_frames), 8, 30)``, vectors are padded to
``T_max = max(T_s)`` using **each syllable's own channel means** for tail dimensions.
This may leak bout length into HDBSCAN; alternatives (global median pad, truncate)
were discussed and deferred. Treat cluster labels as hypothesis-generating.

**Speed units:** ``mean_speed_mps`` is meters per second from legacy ambulation
(``spot``/``centroid`` xy in **pixels**, converted via per-trial ``px_per_cm`` in
``movement_layer._speed_from_xy``). ``t_s`` is seconds.

Per-model example::

    uv run python scratch/kpms_ensemble_compare/syllable_speed_cluster.py \\
        --kpms-root "C:/Users/admin/Documents/work/sack/test2" \\
        --legacy-db "C:/Users/admin/Documents/work/sack/test/vast_results_legacy.h5" \\
        --manifest-path "C:/Users/admin/Documents/work/sack/test2/trial_manifest_kpms_tracking.csv" \\
        --out-dir "C:/Users/admin/Documents/work/sack/test2/block_ethogram_exports" \\
        --models anatomical/seed_042

Per-stream example (all seeds for anatomical)::

    uv run python scratch/kpms_ensemble_compare/syllable_speed_cluster.py \\
        --scope per-stream --models anatomical --phase run \\
        ... (same paths)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, TypeVar

import keypoint_moseq as kpms
import matplotlib.pyplot as plt
import numpy as np

from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.io.file_discovery import load_manifest_csv

_SCRATCH_DIR = Path(__file__).resolve().parent
if str(_SCRATCH_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_DIR))

from block_ethogram_exports import (  # noqa: E402
    LEGEND_FILENAME,
    build_global_occupancy,
    render_global_legend,
    syllable_jet_rgb,
)
from movement_layer import load_ambulation_xy, movement_series_for_trial  # noqa: E402
from behavior_ethogram_phase_i import (  # noqa: E402
    DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
    build_speed_rank_table,
    default_phase_i_out_dir,
    extend_features_tmax,
    parse_stream_jobs,
    prototype_scalars_from_bouts,
)
PhaseKind = Literal["all", "run", "iti"]
MotifStyle = Literal["centroid", "trajectory"]
ScopeKind = Literal["per-model", "per-stream"]
SyllableKey = tuple[str, int]  # (seed, raw_syllable_id) for per-stream pooling

K = TypeVar("K")

T_MIN = 8
T_MAX = 30
PADDING_DISCLAIMER = (
    "Tail pad = per-syllable channel mean (experimental; may leak bout length). "
    "See syllable_speed_cluster.py module docstring."
)

LABEL_FIELDS = (
    "seed",
    "raw_syllable_id",
    "cluster_id",
    "T_s",
    "T_max",
    "n_pad_dims",
    "mean_speed_mps",
    "global_occupancy",
    "n_instances",
    "speed_index",
    "frac_still",
    "mean_abs_dheading",
    "bout_speed_iqr",
    "ambiguous",
)

STREAM_RANK_FIELDS = (
    "seed",
    "raw_syllable_id",
    "speed_index",
    "mean_speed_mps",
    "global_occupancy",
    "cluster_id",
)

INEQUALITY_FIELDS = (
    "stream",
    "seed",
    "phase",
    "cluster_id",
    "n_syllables",
    "n_seeds",
    "mean_speed_min",
    "mean_speed_max",
    "speed_range",
    "occupancy_std",
    "centroid_dispersion",
    "heading_curve_dtw_mean",
    "n_pad_dims_mean",
    "padding_note",
)


def _decode_state(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode().strip()
    return str(value).strip()


def _phase_mask(states: np.ndarray, phase: PhaseKind) -> np.ndarray:
    if phase == "all":
        return np.ones(states.shape[0], dtype=bool)
    if phase == "run":
        return states == "run"
    return states != "run"


def _iter_bouts(
    syll: np.ndarray,
    mask: np.ndarray,
    *,
    min_bout_frames: int,
) -> list[tuple[int, slice]]:
    """Contiguous runs of one syllable ID (>=0) where mask is True."""
    out: list[tuple[int, slice]] = []
    n = syll.size
    i = 0
    while i < n:
        if not mask[i] or syll[i] < 0:
            i += 1
            continue
        sid = int(syll[i])
        j = i + 1
        while j < n and mask[j] and int(syll[j]) == sid:
            j += 1
        if j - i >= min_bout_frames:
            out.append((sid, slice(i, j)))
        i = j
    return out


def _resample_bout(
    speed: np.ndarray,
    heading: np.ndarray,
    *,
    n_points: int,
) -> tuple[np.ndarray, np.ndarray]:
    if n_points <= 0:
        return np.array([]), np.array([])
    if speed.size == 1:
        return np.full(n_points, speed[0]), np.full(n_points, heading[0])
    src = np.linspace(0.0, 1.0, speed.size)
    tgt = np.linspace(0.0, 1.0, n_points)
    sp = np.interp(tgt, src, speed.astype(np.float64))
    cos_h = np.interp(tgt, src, np.cos(heading))
    sin_h = np.interp(tgt, src, np.sin(heading))
    hd = np.arctan2(sin_h, cos_h)
    return sp, hd


def _curve_to_features(speed: np.ndarray, heading: np.ndarray) -> np.ndarray:
    return np.concatenate([speed, np.cos(heading), np.sin(heading)], axis=0)


def _pad_features(vec: np.ndarray, *, t_s: int, t_max: int) -> np.ndarray:
    """Pad 3*t_s vector to 3*t_max using per-channel means (see PADDING EXPERIMENT)."""
    if t_s >= t_max:
        return vec[: 3 * t_max].copy()
    out = np.zeros(3 * t_max, dtype=np.float64)
    out[: 3 * t_s] = vec
    for ch in range(3):
        chunk = vec[ch * t_s : (ch + 1) * t_s]
        fill = float(np.mean(chunk)) if chunk.size else 0.0
        out[ch * t_max + t_s : (ch + 1) * t_max] = fill
    return out


def _dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Simple 1D DTW (small n only)."""
    na, nb = a.size, b.size
    if na == 0 or nb == 0:
        return float("nan")
    cost = np.full((na + 1, nb + 1), np.inf)
    cost[0, 0] = 0.0
    for i in range(1, na + 1):
        for j in range(1, nb + 1):
            d = abs(float(a[i - 1]) - float(b[j - 1]))
            cost[i, j] = d + min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])
    return float(cost[na, nb])


@dataclass
class SyllableStats:
    raw_id: int
    mean_speed: float
    global_occupancy: float
    n_instances: int
    t_s: int
    t_max: int
    features: np.ndarray
    heading_curve: np.ndarray
    centroid_xy: tuple[float, float]
    mean_heading: float
    frac_still: float = 0.0
    mean_abs_dheading: float = 0.0
    bout_speed_iqr: float = 0.0
    ambiguous: bool = False


def _parse_models(raw: list[str] | None) -> list[tuple[str, str]]:
    """Expand CLI model tokens into (stream, seed) pairs."""
    jobs = parse_stream_jobs(raw)
    out: list[tuple[str, str]] = []
    for stream, seeds, _requested in jobs:
        for seed in seeds:
            out.append((stream, seed))
    return out


def align_stats_tmax(
    stats: dict[SyllableKey, SyllableStats],
    t_max: int,
) -> dict[SyllableKey, SyllableStats]:
    out: dict[SyllableKey, SyllableStats] = {}
    for key, st in stats.items():
        if st.t_max == t_max:
            out[key] = st
            continue
        feat = extend_features_tmax(st.features, t_s=st.t_s, t_max_from=st.t_max, t_max_to=t_max)
        out[key] = replace(st, features=feat, t_max=t_max)
    return out


def collect_syllable_kinematics(
    *,
    kpms_root: Path,
    legacy_db: Path,
    manifest_path: Path,
    stream: str,
    seed: str,
    phase: PhaseKind,
    min_bout_frames: int,
    min_occupancy_pct: float,
    tracking_h5: Path | None,
    ambiguous_threshold_mps: float = DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
) -> tuple[dict[int, SyllableStats], int]:
    """Build per-syllable bout curves and metadata."""
    results_path = kpms_root / stream / f"seed_{seed}" / "results_apply.h5"
    global_occ = build_global_occupancy(results_path)
    results = kpms.load_hdf5(str(results_path))
    manifests = {m.kpms_results_dict_key: m for m in load_manifest_csv(manifest_path)}
    track_db = tracking_h5 or (kpms_root / "kpms_tracking.h5")

    pre_cfg = KpmsPreprocessConfig(
        min_fragment_frames=4,
        jump_filter_cm=15.0,
        jump_filter_lookahead_frames=3,
        px_per_cm=2.42,
        retain_all_frames=False,
        db_path=track_db,
        pose_stream=stream,  # type: ignore[arg-type]
    )

    bout_lengths: dict[int, list[int]] = defaultdict(list)
    speed_sums: dict[int, float] = defaultdict(float)
    speed_counts: dict[int, int] = defaultdict(int)
    centroid_pts: dict[int, list[tuple[float, float]]] = defaultdict(list)
    heading_vals: dict[int, list[float]] = defaultdict(list)
    is_moving_frames: dict[int, list[bool]] = defaultdict(list)

    for tkey, rec in results.items():
        manifest = manifests.get(tkey)
        if manifest is None:
            continue
        syll = np.asarray(rec["syllable"]).ravel()
        heading = np.asarray(rec.get("heading", np.zeros_like(syll))).ravel()
        centroid = np.asarray(rec.get("centroid", np.zeros((syll.size, 2)))).reshape(-1, 2)

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
        mask = _phase_mask(states, phase)

        for sid, sl in _iter_bouts(syll, mask, min_bout_frames=min_bout_frames):
            bout_lengths[sid].append(int(sl.stop - sl.start))

        labeled = mask & (syll >= 0)
        for sid in np.unique(syll[labeled].astype(int)):
            sid = int(sid)
            in_sid = labeled & (syll == sid)
            speed_sums[sid] += float(np.sum(mv.speed_mps[in_sid]))
            speed_counts[sid] += int(np.sum(in_sid))
            is_moving_frames[sid].extend(bool(x) for x in mv.is_moving[in_sid])
            for c in centroid[in_sid]:
                if np.isfinite(c).all():
                    centroid_pts[sid].append((float(c[0]), float(c[1])))
            heading_vals[sid].extend(
                float(x) for x in heading[in_sid] if np.isfinite(x)
            )

    if min_occupancy_pct > 0:
        total_frames = sum(speed_counts.values())
        min_frac = min_occupancy_pct / 100.0
        keep_ids = {
            sid
            for sid in speed_counts
            if global_occ.get(sid, 0.0) >= min_frac
            or (total_frames > 0 and speed_counts[sid] / total_frames >= min_frac)
        }
    else:
        keep_ids = set(speed_counts.keys())

    t_by_syll: dict[int, int] = {}
    for sid in keep_ids:
        lengths = bout_lengths.get(sid, [])
        if not lengths:
            continue
        med = float(np.median(lengths))
        t_by_syll[sid] = int(np.clip(round(1.5 * med), T_MIN, T_MAX))

    if not t_by_syll:
        return {}, 0

    t_max = int(max(t_by_syll.values()))
    bout_curves: dict[int, list[np.ndarray]] = defaultdict(list)
    bout_headings: dict[int, list[np.ndarray]] = defaultdict(list)
    bout_mean_speeds: dict[int, list[float]] = defaultdict(list)

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
        mask = _phase_mask(states, phase)

        for sid, sl in _iter_bouts(syll, mask, min_bout_frames=min_bout_frames):
            if sid not in t_by_syll:
                continue
            t_s = t_by_syll[sid]
            sp, hd = _resample_bout(mv.speed_mps[sl], heading[sl], n_points=t_s)
            bout_curves[sid].append(_curve_to_features(sp, hd))
            bout_headings[sid].append(hd)
            bout_mean_speeds[sid].append(float(np.mean(mv.speed_mps[sl])))

    stats: dict[int, SyllableStats] = {}
    for sid, t_s in t_by_syll.items():
        curves = bout_curves.get(sid, [])
        if not curves:
            continue
        med_curve = np.median(np.stack(curves, axis=0), axis=0)
        feat = _pad_features(med_curve, t_s=t_s, t_max=t_max)
        hd_curves = bout_headings.get(sid, [])
        med_heading = (
            np.median(np.stack(hd_curves, axis=0), axis=0) if hd_curves else np.array([])
        )
        pts = centroid_pts.get(sid, [])
        if pts:
            cx = float(np.mean([p[0] for p in pts]))
            cy = float(np.mean([p[1] for p in pts]))
        else:
            cx, cy = 0.0, 0.0
        hlist = heading_vals.get(sid, [])
        mean_h = float(np.arctan2(np.mean(np.sin(hlist)), np.mean(np.cos(hlist)))) if hlist else 0.0
        mean_spd = speed_sums[sid] / max(speed_counts[sid], 1)
        scalars = prototype_scalars_from_bouts(
            is_moving_frames=np.asarray(is_moving_frames.get(sid, []), dtype=bool),
            heading_frames=np.asarray(heading_vals.get(sid, []), dtype=np.float64),
            bout_mean_speeds=bout_mean_speeds.get(sid, []),
            ambiguous_threshold_mps=ambiguous_threshold_mps,
        )
        stats[sid] = SyllableStats(
            raw_id=sid,
            mean_speed=mean_spd,
            global_occupancy=global_occ.get(sid, 0.0),
            n_instances=len(curves),
            t_s=t_s,
            t_max=t_max,
            features=feat,
            heading_curve=med_heading,
            centroid_xy=(cx, cy),
            mean_heading=mean_h,
            frac_still=scalars.frac_still,
            mean_abs_dheading=scalars.mean_abs_dheading,
            bout_speed_iqr=scalars.bout_speed_iqr,
            ambiguous=scalars.ambiguous,
        )
    return stats, t_max


def _zscore_features(matrix: np.ndarray) -> np.ndarray:
    mu = np.nanmean(matrix, axis=0)
    sd = np.nanstd(matrix, axis=0, ddof=1)
    sd = np.where(sd > 0, sd, 1.0)
    return (matrix - mu) / sd


def _sort_stat_keys(keys: list[K]) -> list[K]:
    if not keys:
        return []
    if isinstance(keys[0], tuple):
        return sorted(keys, key=lambda k: (k[0], k[1]))  # type: ignore[index]
    return sorted(keys)  # type: ignore[return-value]


def run_hdbscan(
    stats: dict[K, SyllableStats],
    *,
    min_cluster_size: int | None,
    min_samples: int,
) -> dict[K, int]:
    try:
        import hdbscan
    except ImportError as e:
        raise ImportError(
            "hdbscan is required. Install with: uv sync --extra kpms"
        ) from e

    keys = _sort_stat_keys(list(stats.keys()))
    n = len(keys)
    if n < 2:
        return {keys[0]: 0} if n == 1 else {}
    mcs = min_cluster_size if min_cluster_size is not None else max(3, int(math.ceil(0.02 * n)))
    X = _zscore_features(np.stack([stats[k].features for k in keys], axis=0))
    clusterer = hdbscan.HDBSCAN(min_cluster_size=mcs, min_samples=min_samples)
    labels = clusterer.fit_predict(X)
    return {k: int(lab) for k, lab in zip(keys, labels, strict=True)}


def write_speed_rank_csv(
    path: Path,
    stats: dict[K, SyllableStats],
    clusters: dict[K, int],
    speed_rank: dict[K, int],
    *,
    seed: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    per_seed = seed is not None
    fieldnames = list(STREAM_RANK_FIELDS) if not per_seed else [
        "raw_syllable_id",
        "speed_index",
        "mean_speed_mps",
        "global_occupancy",
        "cluster_id",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for key in _sort_stat_keys(list(stats.keys())):
            st = stats[key]
            raw_id = key[1] if isinstance(key, tuple) else int(key)
            row_seed = key[0] if isinstance(key, tuple) else seed
            row: dict[str, object] = {
                "raw_syllable_id": raw_id,
                "speed_index": speed_rank[key],
                "mean_speed_mps": round(st.mean_speed, 6),
                "global_occupancy": round(st.global_occupancy, 6),
                "cluster_id": clusters.get(key, -1),
            }
            if not per_seed:
                row = {"seed": row_seed, **row}
            w.writerow(row)


def write_hdbscan_labels_csv(
    path: Path,
    stats: dict[K, SyllableStats],
    clusters: dict[K, int],
    speed_rank: dict[K, int],
    *,
    seed: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LABEL_FIELDS)
        w.writeheader()
        for key in _sort_stat_keys(list(stats.keys())):
            st = stats[key]
            raw_id = key[1] if isinstance(key, tuple) else int(key)
            row_seed = key[0] if isinstance(key, tuple) else seed
            w.writerow(
                {
                    "seed": row_seed,
                    "raw_syllable_id": raw_id,
                    "cluster_id": clusters.get(key, -1),
                    "T_s": st.t_s,
                    "T_max": st.t_max,
                    "n_pad_dims": 3 * (st.t_max - st.t_s),
                    "mean_speed_mps": round(st.mean_speed, 6),
                    "global_occupancy": round(st.global_occupancy, 6),
                    "n_instances": st.n_instances,
                    "speed_index": speed_rank[key],
                    "frac_still": round(st.frac_still, 6),
                    "mean_abs_dheading": round(st.mean_abs_dheading, 6),
                    "bout_speed_iqr": round(st.bout_speed_iqr, 6),
                    "ambiguous": int(st.ambiguous),
                }
            )


def _cluster_inequality_rows(
    *,
    stream: str,
    phase: PhaseKind,
    stats: dict[K, SyllableStats],
    clusters: dict[K, int],
    scope: ScopeKind,
    seed: str = "",
) -> list[dict[str, object]]:
    by_cluster: dict[int, list[K]] = defaultdict(list)
    for key, cid in clusters.items():
        by_cluster[cid].append(key)

    rows: list[dict[str, object]] = []
    for cid in sorted(by_cluster.keys()):
        keys = by_cluster[cid]
        speeds = [stats[k].mean_speed for k in keys]
        occs = [stats[k].global_occupancy for k in keys]
        cents = np.array([stats[k].centroid_xy for k in keys], dtype=np.float64)
        centroid_disp = 0.0
        if len(keys) > 1:
            dists = []
            for i in range(len(keys)):
                for j in range(i + 1, len(keys)):
                    dists.append(float(np.linalg.norm(cents[i] - cents[j])))
            centroid_disp = float(np.mean(dists))

        dtw_vals: list[float] = []
        curves = [stats[k].heading_curve for k in keys if stats[k].heading_curve.size]
        for i in range(len(curves)):
            for j in range(i + 1, len(curves)):
                dtw_vals.append(_dtw_distance(curves[i], curves[j]))
        dtw_mean = float(np.mean(dtw_vals)) if dtw_vals else 0.0
        pad_mean = float(np.mean([stats[k].t_max - stats[k].t_s for k in keys]))
        if scope == "per-stream":
            seeds_in_cluster = sorted({k[0] for k in keys if isinstance(k, tuple)})
            seed_cell = ",".join(seeds_in_cluster)
            n_seeds = len(seeds_in_cluster)
        else:
            seed_cell = seed
            n_seeds = 1

        rows.append(
            {
                "stream": stream,
                "seed": seed_cell,
                "phase": phase,
                "cluster_id": cid,
                "n_syllables": len(keys),
                "n_seeds": n_seeds,
                "mean_speed_min": round(min(speeds), 6),
                "mean_speed_max": round(max(speeds), 6),
                "speed_range": round(max(speeds) - min(speeds), 6),
                "occupancy_std": round(float(np.std(occs, ddof=1)) if len(occs) > 1 else 0.0, 6),
                "centroid_dispersion": round(centroid_disp, 6),
                "heading_curve_dtw_mean": round(dtw_mean, 6),
                "n_pad_dims_mean": round(pad_mean, 3),
                "padding_note": PADDING_DISCLAIMER,
            }
        )
    return rows


def _draw_centroid_motif(ax: plt.Axes, st: SyllableStats, *, max_speed_idx: int, speed_rank: int) -> None:
    ax.set_aspect("equal")
    ax.arrow(
        0,
        0,
        0.35 * math.cos(st.mean_heading),
        0.35 * math.sin(st.mean_heading),
        head_width=0.08,
        color=syllable_jet_rgb(speed_rank, max_syllable_id=max_speed_idx),
        length_includes_head=True,
    )
    ax.plot(0, 0, "o", color="black", markersize=3)
    ax.set_xlim(-0.6, 0.6)
    ax.set_ylim(-0.6, 0.6)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(
        f"id{st.raw_id} spd={st.mean_speed:.2f}\nocc={st.global_occupancy:.3f}",
        fontsize=6,
    )


def render_motif_grid(
    path: Path,
    stats: dict[int, SyllableStats],
    clusters: dict[int, int],
    speed_rank: dict[int, int],
    *,
    stream: str,
    seed: str,
    phase: PhaseKind,
    drop_noise: bool,
    motif_style: MotifStyle,
) -> None:
    del motif_style  # trajectory flag reserved for follow-up
    by_cluster: dict[int, list[int]] = defaultdict(list)
    for sid, cid in clusters.items():
        if drop_noise and cid < 0:
            continue
        by_cluster[cid].append(sid)

    def _cluster_mean_speed(cid: int) -> float:
        sids = by_cluster[cid]
        return float(np.mean([stats[s].mean_speed for s in sids])) if sids else 0.0

    cluster_ids = sorted(by_cluster.keys(), key=lambda c: (_cluster_mean_speed(c), c))
    max_speed_idx = max(speed_rank.values()) if speed_rank else 1

    n_rows = len(cluster_ids)
    if n_rows == 0:
        return
    max_cols = max(len(by_cluster[c]) for c in cluster_ids)
    fig, axes = plt.subplots(
        n_rows,
        max_cols,
        figsize=(max(2.0 * max_cols, 6), max(1.8 * n_rows, 4)),
        squeeze=False,
    )
    fig.suptitle(
        f"{stream}/seed_{seed}  phase={phase}  HDBSCAN motif grid\n{PADDING_DISCLAIMER}",
        fontsize=9,
        y=0.98,
    )
    for ri, cid in enumerate(cluster_ids):
        sids = sorted(by_cluster[cid], key=lambda s: (stats[s].mean_speed, s))
        for ci in range(max_cols):
            ax = axes[ri, ci]
            if ci >= len(sids):
                ax.axis("off")
                continue
            sid = sids[ci]
            _draw_centroid_motif(ax, stats[sid], max_speed_idx=max_speed_idx, speed_rank=speed_rank[sid])
        axes[ri, 0].set_ylabel(
            f"c={cid}\nspd {_cluster_mean_speed(cid):.2f}",
            fontsize=7,
        )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def render_stream_motif_grid(
    path: Path,
    stats: dict[SyllableKey, SyllableStats],
    clusters: dict[SyllableKey, int],
    speed_rank: dict[SyllableKey, int],
    *,
    stream: str,
    seeds_ordered: tuple[str, ...],
    phase: PhaseKind,
    drop_noise: bool,
    motif_style: MotifStyle,
) -> None:
    del motif_style
    by_cluster: dict[int, list[SyllableKey]] = defaultdict(list)
    for key, cid in clusters.items():
        if drop_noise and cid < 0:
            continue
        by_cluster[cid].append(key)

    def _cluster_mean_speed(cid: int) -> float:
        keys = by_cluster[cid]
        return float(np.mean([stats[k].mean_speed for k in keys])) if keys else 0.0

    cluster_ids = sorted(by_cluster.keys(), key=lambda c: (_cluster_mean_speed(c), c))
    max_speed_idx = max(speed_rank.values()) if speed_rank else 1
    n_rows = len(cluster_ids)
    if n_rows == 0:
        return

    max_per_block = max(
        (
            len([k for k in by_cluster[cid] if k[0] == seed])
            for cid in cluster_ids
            for seed in seeds_ordered
        ),
        default=1,
    )
    n_blocks = len(seeds_ordered)
    n_cols = n_blocks * max_per_block
    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(max(1.5 * n_cols, 8), max(1.8 * n_rows, 4)),
        squeeze=False,
    )
    fig.suptitle(
        f"{stream} per-stream  phase={phase}  HDBSCAN motif grid\n{PADDING_DISCLAIMER}",
        fontsize=9,
        y=0.98,
    )
    for ri, cid in enumerate(cluster_ids):
        for bi, seed in enumerate(seeds_ordered):
            keys = sorted(
                [k for k in by_cluster[cid] if k[0] == seed],
                key=lambda k: (stats[k].mean_speed, k[1]),
            )
            col0 = bi * max_per_block
            for ci in range(max_per_block):
                ax = axes[ri, col0 + ci]
                if ci >= len(keys):
                    ax.axis("off")
                    continue
                key = keys[ci]
                _draw_centroid_motif(
                    ax,
                    stats[key],
                    max_speed_idx=max_speed_idx,
                    speed_rank=speed_rank[key],
                )
            if keys:
                axes[ri, col0].set_title(f"s{seed}", fontsize=6, loc="left")
        axes[ri, 0].set_ylabel(
            f"c={cid}\nspd {_cluster_mean_speed(cid):.2f}",
            fontsize=7,
        )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def _phase_suffix(phase: PhaseKind) -> str:
    return "" if phase == "all" else f"_{phase}"


def run_model_clustering(
    *,
    kpms_root: Path,
    legacy_db: Path,
    manifest_path: Path,
    out_dir: Path,
    stream: str,
    seed: str,
    phase: PhaseKind,
    min_bout_frames: int,
    min_occupancy_pct: float,
    min_cluster_size: int | None,
    min_samples: int,
    drop_noise: bool,
    motif_style: MotifStyle,
    tracking_h5: Path | None,
    ambiguous_threshold_mps: float = DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
) -> Path:
    model_out = out_dir / stream / f"seed_{seed}"
    model_out.mkdir(parents=True, exist_ok=True)
    suffix = _phase_suffix(phase)

    stats, t_max = collect_syllable_kinematics(
        kpms_root=kpms_root,
        legacy_db=legacy_db,
        manifest_path=manifest_path,
        stream=stream,
        seed=seed,
        phase=phase,
        min_bout_frames=min_bout_frames,
        min_occupancy_pct=min_occupancy_pct,
        tracking_h5=tracking_h5,
        ambiguous_threshold_mps=ambiguous_threshold_mps,
    )
    if not stats:
        raise RuntimeError(f"No syllables passed filters for {stream}/seed_{seed} phase={phase}")

    clusters = run_hdbscan(
        stats,
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
    )
    speed_rank = build_speed_rank_table(stats)

    write_speed_rank_csv(
        model_out / f"speed_rank_table{suffix}.csv",
        stats,
        clusters,
        speed_rank,
        seed=seed,
    )
    write_hdbscan_labels_csv(
        model_out / f"hdbscan_labels{suffix}.csv",
        stats,
        clusters,
        speed_rank,
        seed=seed,
    )

    ineq_rows = _cluster_inequality_rows(
        stream=stream,
        phase=phase,
        stats=stats,
        clusters=clusters,
        scope="per-model",
        seed=seed,
    )
    ineq_path = model_out / f"cluster_inequality{suffix}.csv"
    with ineq_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=INEQUALITY_FIELDS)
        w.writeheader()
        w.writerows(ineq_rows)

    render_motif_grid(
        model_out / f"speed_motif_grid{suffix}.png",
        stats,
        clusters,
        speed_rank,
        stream=stream,
        seed=seed,
        phase=phase,
        drop_noise=drop_noise,
        motif_style=motif_style,
    )

    max_id = max(speed_rank.values()) if speed_rank else 1
    occ_ymax = max(st.mean_speed for st in stats.values()) if stats else 1.0
    ent_ymax = math.log(len(stats)) if len(stats) > 1 else 1.0
    from block_ethogram_exports import ModelPlotLimits

    limits = ModelPlotLimits(
        max_id,
        occ_ymax,
        ent_ymax,
        tuple(sorted(stats.keys(), key=lambda s: speed_rank[s])),
        speed_rank,
    )
    render_global_legend(
        model_out / LEGEND_FILENAME,
        limits=limits,
        model_label=f"{stream}/seed_{seed} speed-rank (T_max={t_max})",
    )
    return model_out


def run_stream_clustering(
    *,
    kpms_root: Path,
    legacy_db: Path,
    manifest_path: Path,
    out_dir: Path,
    stream: str,
    seeds: tuple[str, ...],
    seeds_requested: tuple[str, ...],
    phase: PhaseKind,
    min_bout_frames: int,
    min_occupancy_pct: float,
    min_cluster_size: int | None,
    min_samples: int,
    drop_noise: bool,
    motif_style: MotifStyle,
    tracking_h5: Path | None,
    ambiguous_threshold_mps: float = DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
) -> Path:
    shared_out = out_dir / stream / "shared"
    shared_out.mkdir(parents=True, exist_ok=True)
    suffix = _phase_suffix(phase)

    keyed: dict[SyllableKey, SyllableStats] = {}
    per_seed_tmax: list[int] = []
    for seed in seeds:
        stats, t_max = collect_syllable_kinematics(
            kpms_root=kpms_root,
            legacy_db=legacy_db,
            manifest_path=manifest_path,
            stream=stream,
            seed=seed,
            phase=phase,
            min_bout_frames=min_bout_frames,
            min_occupancy_pct=min_occupancy_pct,
            tracking_h5=tracking_h5,
            ambiguous_threshold_mps=ambiguous_threshold_mps,
        )
        if not stats:
            print(f"Warning: no syllables for {stream}/seed_{seed} phase={phase}")
            continue
        per_seed_tmax.append(t_max)
        for raw_id, st in stats.items():
            keyed[(seed, int(raw_id))] = st

    if not keyed:
        raise RuntimeError(f"No syllables passed filters for stream {stream} phase={phase}")

    stream_t_max = max(st.t_max for st in keyed.values())
    keyed = align_stats_tmax(keyed, stream_t_max)

    clusters = run_hdbscan(
        keyed,
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
    )
    speed_rank = build_speed_rank_table(keyed)

    write_speed_rank_csv(
        shared_out / f"speed_rank_table{suffix}.csv",
        keyed,
        clusters,
        speed_rank,
    )
    write_hdbscan_labels_csv(
        shared_out / f"hdbscan_labels{suffix}.csv",
        keyed,
        clusters,
        speed_rank,
    )

    ineq_rows = _cluster_inequality_rows(
        stream=stream,
        phase=phase,
        stats=keyed,
        clusters=clusters,
        scope="per-stream",
    )
    ineq_path = shared_out / f"cluster_inequality{suffix}.csv"
    with ineq_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=INEQUALITY_FIELDS)
        w.writeheader()
        w.writerows(ineq_rows)

    seeds_included = tuple(dict.fromkeys(k[0] for k in keyed.keys()))
    render_stream_motif_grid(
        shared_out / f"speed_motif_grid{suffix}.png",
        keyed,
        clusters,
        speed_rank,
        stream=stream,
        seeds_ordered=seeds_included,
        phase=phase,
        drop_noise=drop_noise,
        motif_style=motif_style,
    )

    max_id = max(speed_rank.values()) if speed_rank else 1
    occ_ymax = max(st.mean_speed for st in keyed.values())
    ent_ymax = math.log(len(keyed)) if len(keyed) > 1 else 1.0
    from block_ethogram_exports import ModelPlotLimits

    limits = ModelPlotLimits(
        max_id,
        occ_ymax,
        ent_ymax,
        tuple(range(max_id + 1)),
        None,
    )
    render_global_legend(
        shared_out / LEGEND_FILENAME,
        limits=limits,
        model_label=f"{stream} stream speed-rank (T_max={stream_t_max})",
    )

    run_meta = {
        "stream": stream,
        "scope": "per-stream",
        "phase": phase,
        "T_max": stream_t_max,
        "seeds_requested": list(seeds_requested),
        "seeds_included": list(seeds_included),
        "seeds_skipped": [s for s in seeds_requested if s not in seeds_included],
        "n_syllables": len(keyed),
        "padding_note": PADDING_DISCLAIMER,
    }
    (shared_out / f"cluster_run{suffix}.json").write_text(
        json.dumps(run_meta, indent=2),
        encoding="utf-8",
    )

    for seed in seeds_included:
        seed_stats = {int(k[1]): keyed[k] for k in keyed if k[0] == seed}
        seed_clusters = {int(k[1]): clusters[k] for k in keyed if k[0] == seed}
        seed_rank = {int(k[1]): speed_rank[k] for k in keyed if k[0] == seed}
        seed_out = out_dir / stream / f"seed_{seed}"
        seed_out.mkdir(parents=True, exist_ok=True)
        write_speed_rank_csv(
            seed_out / f"speed_rank_table{suffix}.csv",
            seed_stats,
            seed_clusters,
            seed_rank,
            seed=seed,
        )

    return shared_out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kpms-root", type=Path, required=True)
    parser.add_argument("--legacy-db", type=Path, required=True)
    parser.add_argument("--manifest-path", type=Path, required=True)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output root (default: {kpms_root}/behavior_ethogram/phase_i)",
    )
    parser.add_argument("--tracking-h5", type=Path, default=None)
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument(
        "--phase",
        choices=("all", "run", "iti"),
        default="all",
    )
    parser.add_argument("--min-bout-frames", type=int, default=4)
    parser.add_argument(
        "--min-occupancy",
        type=float,
        default=0.1,
        help="Min cohort occupancy %% to keep syllable (0=off)",
    )
    parser.add_argument("--min-cluster-size", type=int, default=None)
    parser.add_argument("--min-samples", type=int, default=2)
    parser.add_argument("--drop-noise", action="store_true")
    parser.add_argument(
        "--scope",
        choices=("per-model", "per-stream"),
        default="per-model",
        help="per-model: cluster within each seed; per-stream: pool seeds then project ranks",
    )
    parser.add_argument(
        "--motif-style",
        choices=("centroid", "trajectory"),
        default="centroid",
    )
    parser.add_argument(
        "--ambiguous-bout-speed-iqr",
        type=float,
        default=DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
        help="Prototype bout speed IQR above this marks ambiguous (ADR 0007)",
    )
    args = parser.parse_args()

    kpms_root = args.kpms_root.expanduser().resolve()
    legacy_db = args.legacy_db.expanduser().resolve()
    manifest_path = args.manifest_path.expanduser().resolve()
    out_dir = (args.out_dir or default_phase_i_out_dir(kpms_root)).expanduser().resolve()
    tracking_h5 = args.tracking_h5.expanduser().resolve() if args.tracking_h5 else None
    phase: PhaseKind = args.phase  # type: ignore[assignment]
    motif: MotifStyle = args.motif_style  # type: ignore[assignment]
    scope: ScopeKind = args.scope  # type: ignore[assignment]

    if scope == "per-stream":
        jobs = parse_stream_jobs(args.models, kpms_root=kpms_root)
        for stream, seeds, seeds_requested in jobs:
            out = run_stream_clustering(
                kpms_root=kpms_root,
                legacy_db=legacy_db,
                manifest_path=manifest_path,
                out_dir=out_dir,
                stream=stream,
                seeds=seeds,
                seeds_requested=seeds_requested,
                phase=phase,
                min_bout_frames=args.min_bout_frames,
                min_occupancy_pct=args.min_occupancy,
                min_cluster_size=args.min_cluster_size,
                min_samples=args.min_samples,
                drop_noise=args.drop_noise,
                motif_style=motif,
                tracking_h5=tracking_h5,
                ambiguous_threshold_mps=args.ambiguous_bout_speed_iqr,
            )
            print(f"Wrote per-stream clustering -> {out}")
    else:
        models = _parse_models(args.models)
        for stream, seed in models:
            if not (kpms_root / stream / f"seed_{seed}" / "results_apply.h5").is_file():
                print(f"Skipping {stream}/seed_{seed}: missing results_apply.h5")
                continue
            out = run_model_clustering(
                kpms_root=kpms_root,
                legacy_db=legacy_db,
                manifest_path=manifest_path,
                out_dir=out_dir,
                stream=stream,
                seed=seed,
                phase=phase,
                min_bout_frames=args.min_bout_frames,
                min_occupancy_pct=args.min_occupancy,
                min_cluster_size=args.min_cluster_size,
                min_samples=args.min_samples,
                drop_noise=args.drop_noise,
                motif_style=motif,
                tracking_h5=tracking_h5,
                ambiguous_threshold_mps=args.ambiguous_bout_speed_iqr,
            )
            print(f"Wrote clustering artifacts -> {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
