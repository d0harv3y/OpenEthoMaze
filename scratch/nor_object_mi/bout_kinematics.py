"""Syllable-bout kinematics on NOR spot + kpMS heading (scratch).

Ethogram-parity names where commensurate; not ``bout_feature_v2`` compile.
Spot is always recomputed from SLEAP; do not read archived ladder CSVs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping, Sequence

import h5py
import numpy as np

from maze.kpms.behavior_ethogram.bout_kinematics import abs_dheading_per_frame
from maze.kpms.behavior_ethogram.bout_scalars import (
    DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
    bout_ambiguous,
    bout_iqr,
    bout_net_dheading_rad,
    bout_straightness,
    circular_mean_sin_cos,
    syllable_runs,
)

from .fam_nvl import fam_nvl_map_for_session
from .join_keys import JoinedSession
from .pseudo_loci import loci_for_animal_phase
from .spot_xy import (
    _node_xy,
    all_object_distances_m,
    nearest_distance_m,
    pixels_per_meter,
    role_distances_m,
    spot_xy_m,
)
from .syllable_cleanup import maybe_absorb_short_bouts

_SS_RE = re.compile(r"_ss-(\d+)(?:_|$)")

PHASES: tuple[str, ...] = ("NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr")
CONDITIONS: frozenset[str] = frozenset({"novel_obj", "identical_obj", "no_obj"})

KINEMATICS_FIELDS: tuple[str, ...] = (
    "model",
    "ss",
    "kpms_key",
    "animal_id",
    "raw_session",
    "phase_layer",
    "condition_layer",
    "tx",
    "sex",
    "cohort",
    "bout_index",
    "raw_syllable_id",
    "row_start",
    "row_end_exclusive",
    "bout_frames",
    "fps",
    "bout_duration_s",
    "bout_mean_speed_mps",
    "bout_iqr_speed_mps",
    "bout_path_length_m",
    "bout_straightness",
    "bout_mean_abs_dheading",
    "bout_iqr_abs_dheading",
    "bout_net_dheading_rad",
    "bout_mean_heading_sin",
    "bout_mean_heading_cos",
    "ambiguous",
    "bout_valid_frame_frac",
    "bout_mean_nose_tail_m",
    "bout_iqr_nose_tail_m",
    "bout_mean_dist_any_m",
    "bout_mean_dist_fam_m",
    "bout_mean_dist_nvl_m",
    "bout_mean_dist_obj_a_m",
    "bout_mean_dist_obj_b_m",
)


def model_num_states(model: str) -> int | float:
    """Parse kpMS alphabet size ``ss`` from ``paramscan_*_ss-N`` names."""
    m = _SS_RE.search(str(model))
    return int(m.group(1)) if m else float("nan")


def session_fps(session: h5py.Group, *, default: float = 30.0) -> float:
    raw = session.attrs.get("video_fps")
    if raw is None:
        return float(default)
    fps = float(np.asarray(raw).item())
    return fps if np.isfinite(fps) and fps > 0 else float(default)


def spot_speed_mps(
    x_m: np.ndarray,
    y_m: np.ndarray,
    valid: np.ndarray,
    fps: float,
) -> np.ndarray:
    """Per-frame spot speed (m/s). Frame 0 NaN; invalid step endpoints → NaN."""
    x = np.asarray(x_m, dtype=np.float64).ravel()
    y = np.asarray(y_m, dtype=np.float64).ravel()
    v = np.asarray(valid, dtype=bool).ravel()
    n = int(x.shape[0])
    out = np.full(n, np.nan, dtype=np.float64)
    if n < 2 or not np.isfinite(fps) or fps <= 0:
        return out
    step = np.hypot(np.diff(x), np.diff(y))
    ok = v[:-1] & v[1:] & np.isfinite(step)
    speeds = np.full(n - 1, np.nan, dtype=np.float64)
    speeds[ok] = step[ok] * float(fps)
    out[1:] = speeds
    return out


def spot_step_length_m(
    x_m: np.ndarray,
    y_m: np.ndarray,
    valid: np.ndarray,
) -> np.ndarray:
    """Per-frame step length into this frame (m). Frame 0 NaN."""
    x = np.asarray(x_m, dtype=np.float64).ravel()
    y = np.asarray(y_m, dtype=np.float64).ravel()
    v = np.asarray(valid, dtype=bool).ravel()
    n = int(x.shape[0])
    out = np.full(n, np.nan, dtype=np.float64)
    if n < 2:
        return out
    step = np.hypot(np.diff(x), np.diff(y))
    ok = v[:-1] & v[1:] & np.isfinite(step)
    lengths = np.full(n - 1, np.nan, dtype=np.float64)
    lengths[ok] = step[ok]
    out[1:] = lengths
    return out


def nose_tail_length_m(session: h5py.Group) -> tuple[np.ndarray, float]:
    """Per-frame nose→tail Euclidean length (m); invalid → NaN. Also returns ppm."""
    if "sleap_data" not in session:
        raise KeyError("sleap_data missing")
    sleap = session["sleap_data"]
    for node in ("nose", "tail"):
        if node not in sleap:
            raise KeyError(f"nose_tail requires sleap node {node!r}")

    nx, ny, nv = _node_xy(sleap, "nose")
    tx, ty, tv = _node_xy(sleap, "tail")
    ppm = pixels_per_meter(session)
    ok = nv & tv & np.isfinite(nx) & np.isfinite(ny) & np.isfinite(tx) & np.isfinite(ty)
    out = np.full(nx.shape, np.nan, dtype=np.float64)
    out[ok] = np.hypot(nx[ok] - tx[ok], ny[ok] - ty[ok]) / ppm
    return out, ppm


def _bout_mean(arr: np.ndarray, start: int, end: int) -> float:
    sl = arr[start:end]
    finite = sl[np.isfinite(sl)]
    if finite.size == 0:
        return float("nan")
    return float(np.mean(finite))


def _bout_sum(arr: np.ndarray, start: int, end: int) -> float:
    sl = arr[start:end]
    finite = sl[np.isfinite(sl)]
    if finite.size == 0:
        return float("nan")
    return float(np.sum(finite))


def _align_len(*arrays: np.ndarray) -> tuple[np.ndarray, ...]:
    n = min(int(a.shape[0]) for a in arrays)
    return tuple(a[:n] for a in arrays)


def _nan_like(ref: np.ndarray) -> np.ndarray:
    return np.full(ref.shape, np.nan, dtype=np.float64)


def proximity_channels(
    nor_h5: h5py.File,
    session: h5py.Group,
    js: JoinedSession,
    *,
    loci_cache: dict[tuple[str, str], np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]:
    """Return d_any, d_fam, d_nvl, d_obj_a, d_obj_b, and a short source tag."""
    cond = js.condition_layer
    if cond == "novel_obj":
        role_map = fam_nvl_map_for_session(nor_h5, js.animal_id, js.raw_session)
        if not role_map:
            raise ValueError("fam_nvl_map_failed")
        d_fam, d_nvl, _ = role_distances_m(session, role_map)
        obj_keys, obj_dists, _ = all_object_distances_m(session)
        if len(obj_keys) < 2:
            raise ValueError(f"need >=2 objects, got {len(obj_keys)}")
        d_a, d_b = obj_dists[0], obj_dists[1]
        d_any = np.minimum(d_a, d_b)
        return d_any, d_fam, d_nvl, d_a, d_b, "real_objects"

    if cond == "identical_obj":
        obj_keys, obj_dists, _ = all_object_distances_m(session)
        if len(obj_keys) < 2:
            raise ValueError(f"need >=2 objects, got {len(obj_keys)}")
        d_a, d_b = obj_dists[0], obj_dists[1]
        d_any = np.minimum(d_a, d_b)
        return d_any, _nan_like(d_a), _nan_like(d_a), d_a, d_b, "real_objects"

    if cond == "no_obj":
        key = (js.animal_id, js.phase_layer)
        if key not in loci_cache:
            loci = loci_for_animal_phase(nor_h5, js.animal_id, js.phase_layer)
            if loci is None:
                raise ValueError("spatial_loci_unavailable")
            loci_cache[key] = loci
        loci = loci_cache[key]
        d_any, _ = nearest_distance_m(session, [loci[0], loci[1]])
        return d_any, _nan_like(d_any), _nan_like(d_any), _nan_like(d_any), _nan_like(d_any), "pseudo_loci"

    raise ValueError(f"unhandled condition_layer {cond!r}")


def sleap_heading_rad(session: h5py.Group) -> np.ndarray:
    """Per-frame heading (rad) from SLEAP nose − spine; invalid → NaN.

    Not kpMS apply heading. Used for movement bouts, which have no model key.
    """
    if "sleap_data" not in session:
        raise KeyError("sleap_data missing")
    sleap = session["sleap_data"]
    nx, ny, nv = _node_xy(sleap, "nose")
    sx, sy, sv = _node_xy(sleap, "spine")
    ok = nv & sv & np.isfinite(nx) & np.isfinite(ny) & np.isfinite(sx) & np.isfinite(sy)
    out = np.full(nx.shape, np.nan, dtype=np.float64)
    out[ok] = np.arctan2(ny[ok] - sy[ok], nx[ok] - sx[ok])
    return out


def movement_bout_spans(
    session: h5py.Group,
    *,
    node: str = "spot",
) -> list[tuple[int, int, int]]:
    """Return ``(bout_index, start, end_exclusive)`` from NOR movement_bouts.

    ``end_frame`` is exclusive (duration_frames == end − start).
    """
    recs = session["ambulation_metrics"][node]["movement_bouts"][()]
    return spans_from_movement_recs(recs)


def spans_from_movement_recs(recs: np.ndarray) -> list[tuple[int, int, int]]:
    """Parse ``(bout_index, start, end_exclusive)`` from a movement_bouts recarray."""
    out: list[tuple[int, int, int]] = []
    names = recs.dtype.names or ()
    if "start_frame" not in names or "end_frame" not in names:
        raise KeyError(f"movement_bouts missing start/end_frame; fields={names}")
    for i, rec in enumerate(recs):
        start = int(rec["start_frame"])
        end = int(rec["end_frame"])
        if end <= start:
            continue
        out.append((i, start, end))
    return out


def immobile_spans_from_movement(
    movement: Sequence[tuple[int, int, int]],
    n_frames: int,
) -> list[tuple[int, int, int]]:
    """Complement of exclusive movement spans on ``[0, n_frames)``.

    Overlapping / nested movement intervals are merged first. Adjacent
    movement (end == next start) yields no gap. A session with no movement
    is one immobile span covering the whole length.
    """
    n = int(n_frames)
    if n <= 0:
        return []
    intervals = []
    for _i, start, end in movement:
        s = max(0, int(start))
        e = min(n, int(end))
        if e > s:
            intervals.append((s, e))
    intervals.sort()
    merged: list[tuple[int, int]] = []
    for s, e in intervals:
        if not merged or s > merged[-1][1]:
            merged.append((s, e))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
    gaps: list[tuple[int, int, int]] = []
    cursor = 0
    idx = 0
    for s, e in merged:
        if s > cursor:
            gaps.append((idx, cursor, s))
            idx += 1
        cursor = max(cursor, e)
    if cursor < n:
        gaps.append((idx, cursor, n))
    return gaps


def _kinematics_row(
    *,
    js: JoinedSession,
    model: str,
    ss: int | float,
    bout_index: int,
    raw_syllable_id: int,
    start: int,
    end: int,
    fps: float,
    speed: np.ndarray,
    step_m: np.ndarray,
    heading: np.ndarray,
    abs_dh: np.ndarray,
    xy: np.ndarray,
    valid: np.ndarray,
    nose_tail: np.ndarray,
    d_any: np.ndarray,
    d_fam: np.ndarray,
    d_nvl: np.ndarray,
    d_a: np.ndarray,
    d_b: np.ndarray,
    ambiguous_threshold_mps: float,
) -> dict[str, object]:
    speed_sl = speed[start:end]
    dh_sl = abs_dh[start:end]
    nt_sl = nose_tail[start:end]
    h_sl = heading[start:end]
    valid_sl = valid[start:end]
    n_frames = int(end - start)
    speed_iqr = bout_iqr(speed_sl)
    mean_sin, mean_cos = circular_mean_sin_cos(h_sl)
    finite_speed = speed_sl[np.isfinite(speed_sl)]
    mean_speed = float(np.mean(finite_speed)) if finite_speed.size else float("nan")
    finite_dh = dh_sl[np.isfinite(dh_sl)]
    mean_dh = float(np.mean(finite_dh)) if finite_dh.size else float("nan")
    return {
        "model": model,
        "ss": ss,
        "kpms_key": js.kpms_key,
        "animal_id": js.animal_id,
        "raw_session": js.raw_session,
        "phase_layer": js.phase_layer,
        "condition_layer": js.condition_layer,
        "tx": js.tx,
        "sex": js.sex,
        "cohort": js.cohort,
        "bout_index": bout_index,
        "raw_syllable_id": int(raw_syllable_id),
        "row_start": int(start),
        "row_end_exclusive": int(end),
        "bout_frames": n_frames,
        "fps": fps,
        "bout_duration_s": float(n_frames) / float(fps) if fps > 0 else float("nan"),
        "bout_mean_speed_mps": mean_speed,
        "bout_iqr_speed_mps": speed_iqr,
        "bout_path_length_m": _bout_sum(step_m, start, end),
        "bout_straightness": bout_straightness(xy[start:end]),
        "bout_mean_abs_dheading": mean_dh,
        "bout_iqr_abs_dheading": bout_iqr(dh_sl),
        "bout_net_dheading_rad": bout_net_dheading_rad(h_sl),
        "bout_mean_heading_sin": mean_sin,
        "bout_mean_heading_cos": mean_cos,
        "ambiguous": int(bout_ambiguous(speed_iqr, threshold_mps=ambiguous_threshold_mps)),
        "bout_valid_frame_frac": (
            float(np.mean(valid_sl.astype(np.float64))) if n_frames else float("nan")
        ),
        "bout_mean_nose_tail_m": _bout_mean(nose_tail, start, end),
        "bout_iqr_nose_tail_m": bout_iqr(nt_sl),
        "bout_mean_dist_any_m": _bout_mean(d_any, start, end),
        "bout_mean_dist_fam_m": _bout_mean(d_fam, start, end),
        "bout_mean_dist_nvl_m": _bout_mean(d_nvl, start, end),
        "bout_mean_dist_obj_a_m": _bout_mean(d_a, start, end),
        "bout_mean_dist_obj_b_m": _bout_mean(d_b, start, end),
    }


def build_kinematics_bout_rows(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    sessions: Sequence[JoinedSession],
    *,
    model: str,
    min_bout_frames: int | None = None,
    loci_cache: Mapping[tuple[str, str], np.ndarray] | None = None,
    ambiguous_threshold_mps: float = DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Collapse kpMS syllables to bouts; attach spot/heading kinematics + proximity."""
    rows: list[dict[str, object]] = []
    cache: dict[tuple[str, str], np.ndarray] = dict(loci_cache or {})
    ss = model_num_states(model)
    n_ok = 0
    n_skip_cond = 0
    n_skip_phase = 0
    n_skip_err = 0
    errors: list[dict[str, str]] = []
    fps_values: list[float] = []

    for js in sessions:
        if js.phase_layer not in PHASES:
            n_skip_phase += 1
            continue
        if js.condition_layer not in CONDITIONS:
            n_skip_cond += 1
            continue
        try:
            sg = nor_h5[js.animal_id][js.raw_session]
            kg = kpms_h5[js.kpms_key]
            syll = maybe_absorb_short_bouts(kg["syllable"][()], min_bout_frames)
            heading = np.asarray(kg["heading"][()], dtype=np.float64).ravel()

            fps = session_fps(sg)
            fps_values.append(fps)
            x_m, y_m, valid, _ppm = spot_xy_m(sg)
            nose_tail, _ = nose_tail_length_m(sg)
            speed = spot_speed_mps(x_m, y_m, valid, fps)
            step_m = spot_step_length_m(x_m, y_m, valid)

            d_any, d_fam, d_nvl, d_a, d_b, _src = proximity_channels(
                nor_h5, sg, js, loci_cache=cache
            )

            (
                syll,
                heading,
                x_m,
                y_m,
                valid,
                speed,
                step_m,
                nose_tail,
                d_any,
                d_fam,
                d_nvl,
                d_a,
                d_b,
            ) = _align_len(
                syll,
                heading,
                x_m,
                y_m,
                valid,
                speed,
                step_m,
                nose_tail,
                d_any,
                d_fam,
                d_nvl,
                d_a,
                d_b,
            )
            abs_dh = abs_dheading_per_frame(heading)
            xy = np.column_stack([x_m, y_m])

            for bout_index, (sid, start, end) in enumerate(syllable_runs(syll)):
                speed_sl = speed[start:end]
                dh_sl = abs_dh[start:end]
                nt_sl = nose_tail[start:end]
                h_sl = heading[start:end]
                valid_sl = valid[start:end]
                n_frames = int(end - start)
                speed_iqr = bout_iqr(speed_sl)
                mean_sin, mean_cos = circular_mean_sin_cos(h_sl)
                finite_speed = speed_sl[np.isfinite(speed_sl)]
                mean_speed = float(np.mean(finite_speed)) if finite_speed.size else float("nan")
                finite_dh = dh_sl[np.isfinite(dh_sl)]
                mean_dh = float(np.mean(finite_dh)) if finite_dh.size else float("nan")

                rows.append(
                    {
                        "model": model,
                        "ss": ss,
                        "kpms_key": js.kpms_key,
                        "animal_id": js.animal_id,
                        "raw_session": js.raw_session,
                        "phase_layer": js.phase_layer,
                        "condition_layer": js.condition_layer,
                        "tx": js.tx,
                        "sex": js.sex,
                        "cohort": js.cohort,
                        "bout_index": bout_index,
                        "raw_syllable_id": int(sid),
                        "row_start": int(start),
                        "row_end_exclusive": int(end),
                        "bout_frames": n_frames,
                        "fps": fps,
                        "bout_duration_s": float(n_frames) / float(fps) if fps > 0 else float("nan"),
                        "bout_mean_speed_mps": mean_speed,
                        "bout_iqr_speed_mps": speed_iqr,
                        "bout_path_length_m": _bout_sum(step_m, start, end),
                        "bout_straightness": bout_straightness(xy[start:end]),
                        "bout_mean_abs_dheading": mean_dh,
                        "bout_iqr_abs_dheading": bout_iqr(dh_sl),
                        "bout_net_dheading_rad": bout_net_dheading_rad(h_sl),
                        "bout_mean_heading_sin": mean_sin,
                        "bout_mean_heading_cos": mean_cos,
                        "ambiguous": int(
                            bout_ambiguous(speed_iqr, threshold_mps=ambiguous_threshold_mps)
                        ),
                        "bout_valid_frame_frac": (
                            float(np.mean(valid_sl.astype(np.float64))) if n_frames else float("nan")
                        ),
                        "bout_mean_nose_tail_m": _bout_mean(nose_tail, start, end),
                        "bout_iqr_nose_tail_m": bout_iqr(nt_sl),
                        "bout_mean_dist_any_m": _bout_mean(d_any, start, end),
                        "bout_mean_dist_fam_m": _bout_mean(d_fam, start, end),
                        "bout_mean_dist_nvl_m": _bout_mean(d_nvl, start, end),
                        "bout_mean_dist_obj_a_m": _bout_mean(d_a, start, end),
                        "bout_mean_dist_obj_b_m": _bout_mean(d_b, start, end),
                    }
                )
            n_ok += 1
        except Exception as exc:  # noqa: BLE001 — scratch: record and continue
            n_skip_err += 1
            errors.append(
                {
                    "animal_id": js.animal_id,
                    "raw_session": js.raw_session,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )

    fps_arr = np.asarray(fps_values, dtype=np.float64)
    summary = {
        "model": model,
        "ss": ss,
        "n_bout_rows": len(rows),
        "n_sessions_ok": n_ok,
        "n_skip_condition": n_skip_cond,
        "n_skip_phase": n_skip_phase,
        "n_skip_error": n_skip_err,
        "min_bout_frames": min_bout_frames,
        "syllable_cleanup": (
            f"absorb_short_bouts<{min_bout_frames}"
            if min_bout_frames is not None and int(min_bout_frames) > 1
            else "none"
        ),
        "fps_median": float(np.median(fps_arr)) if fps_arr.size else float("nan"),
        "fps_min": float(np.min(fps_arr)) if fps_arr.size else float("nan"),
        "fps_max": float(np.max(fps_arr)) if fps_arr.size else float("nan"),
        "n_loci_cache": len(cache),
        "errors": errors[:50],
        "n_errors_truncated": max(0, len(errors) - 50),
    }
    return rows, summary


def build_movement_kinematics_bout_rows(
    nor_h5: h5py.File,
    sessions: Sequence[JoinedSession],
    *,
    node: str = "spot",
    loci_cache: Mapping[tuple[str, str], np.ndarray] | None = None,
    ambiguous_threshold_mps: float = DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Movement-only wrapper; see ``build_ambulation_kinematics_bout_rows``."""
    move_rows, _immobile, summary = build_ambulation_kinematics_bout_rows(
        nor_h5,
        sessions,
        node=node,
        loci_cache=loci_cache,
        ambiguous_threshold_mps=ambiguous_threshold_mps,
    )
    return move_rows, summary


def build_ambulation_kinematics_bout_rows(
    nor_h5: h5py.File,
    sessions: Sequence[JoinedSession],
    *,
    node: str = "spot",
    loci_cache: Mapping[tuple[str, str], np.ndarray] | None = None,
    ambiguous_threshold_mps: float = DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Spot kinematics on movement spans and their immobile complement.

    Heading is SLEAP nose−spine (not kpMS).
    Movement: ``model=movement_{node}``, ``raw_syllable_id=-1``.
    Immobile: ``model=immobile_{node}``, ``raw_syllable_id=-2``.
    """
    move_rows: list[dict[str, object]] = []
    immobile_rows: list[dict[str, object]] = []
    cache: dict[tuple[str, str], np.ndarray] = dict(loci_cache or {})
    move_model = f"movement_{node}"
    still_model = f"immobile_{node}"
    n_ok = 0
    n_skip_cond = 0
    n_skip_phase = 0
    n_skip_err = 0
    errors: list[dict[str, str]] = []
    fps_values: list[float] = []

    def _append(
        dest: list[dict[str, object]],
        *,
        model: str,
        bout_index: int,
        raw_syllable_id: int,
        start: int,
        end: int,
        js: JoinedSession,
        fps: float,
        speed: np.ndarray,
        step_m: np.ndarray,
        heading: np.ndarray,
        abs_dh: np.ndarray,
        xy: np.ndarray,
        valid: np.ndarray,
        nose_tail: np.ndarray,
        d_any: np.ndarray,
        d_fam: np.ndarray,
        d_nvl: np.ndarray,
        d_a: np.ndarray,
        d_b: np.ndarray,
    ) -> None:
        dest.append(
            _kinematics_row(
                js=js,
                model=model,
                ss=float("nan"),
                bout_index=bout_index,
                raw_syllable_id=raw_syllable_id,
                start=start,
                end=end,
                fps=fps,
                speed=speed,
                step_m=step_m,
                heading=heading,
                abs_dh=abs_dh,
                xy=xy,
                valid=valid,
                nose_tail=nose_tail,
                d_any=d_any,
                d_fam=d_fam,
                d_nvl=d_nvl,
                d_a=d_a,
                d_b=d_b,
                ambiguous_threshold_mps=ambiguous_threshold_mps,
            )
        )

    for js in sessions:
        if js.phase_layer not in PHASES:
            n_skip_phase += 1
            continue
        if js.condition_layer not in CONDITIONS:
            n_skip_cond += 1
            continue
        try:
            sg = nor_h5[js.animal_id][js.raw_session]
            fps = session_fps(sg)
            fps_values.append(fps)
            x_m, y_m, valid, _ppm = spot_xy_m(sg)
            heading = sleap_heading_rad(sg)
            nose_tail, _ = nose_tail_length_m(sg)
            speed = spot_speed_mps(x_m, y_m, valid, fps)
            step_m = spot_step_length_m(x_m, y_m, valid)
            d_any, d_fam, d_nvl, d_a, d_b, _src = proximity_channels(
                nor_h5, sg, js, loci_cache=cache
            )
            (
                heading,
                x_m,
                y_m,
                valid,
                speed,
                step_m,
                nose_tail,
                d_any,
                d_fam,
                d_nvl,
                d_a,
                d_b,
            ) = _align_len(
                heading,
                x_m,
                y_m,
                valid,
                speed,
                step_m,
                nose_tail,
                d_any,
                d_fam,
                d_nvl,
                d_a,
                d_b,
            )
            n = int(valid.shape[0])
            abs_dh = abs_dheading_per_frame(heading)
            xy = np.column_stack([x_m, y_m])
            move_spans = movement_bout_spans(sg, node=node)
            for bout_index, start, end in move_spans:
                start_i = max(0, int(start))
                end_i = min(n, int(end))
                if end_i <= start_i:
                    continue
                _append(
                    move_rows,
                    model=move_model,
                    bout_index=bout_index,
                    raw_syllable_id=-1,
                    start=start_i,
                    end=end_i,
                    js=js,
                    fps=fps,
                    speed=speed,
                    step_m=step_m,
                    heading=heading,
                    abs_dh=abs_dh,
                    xy=xy,
                    valid=valid,
                    nose_tail=nose_tail,
                    d_any=d_any,
                    d_fam=d_fam,
                    d_nvl=d_nvl,
                    d_a=d_a,
                    d_b=d_b,
                )
            for bout_index, start, end in immobile_spans_from_movement(move_spans, n):
                _append(
                    immobile_rows,
                    model=still_model,
                    bout_index=bout_index,
                    raw_syllable_id=-2,
                    start=start,
                    end=end,
                    js=js,
                    fps=fps,
                    speed=speed,
                    step_m=step_m,
                    heading=heading,
                    abs_dh=abs_dh,
                    xy=xy,
                    valid=valid,
                    nose_tail=nose_tail,
                    d_any=d_any,
                    d_fam=d_fam,
                    d_nvl=d_nvl,
                    d_a=d_a,
                    d_b=d_b,
                )
            n_ok += 1
        except Exception as exc:  # noqa: BLE001 — scratch: record and continue
            n_skip_err += 1
            errors.append(
                {
                    "animal_id": js.animal_id,
                    "raw_session": js.raw_session,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )

    fps_arr = np.asarray(fps_values, dtype=np.float64)
    summary = {
        "movement_model": move_model,
        "immobile_model": still_model,
        "node": node,
        "ss": float("nan"),
        "heading_source": "sleap_nose_minus_spine",
        "n_movement_rows": len(move_rows),
        "n_immobile_rows": len(immobile_rows),
        "n_bout_rows": len(move_rows),
        "n_sessions_ok": n_ok,
        "n_skip_condition": n_skip_cond,
        "n_skip_phase": n_skip_phase,
        "n_skip_error": n_skip_err,
        "fps_median": float(np.median(fps_arr)) if fps_arr.size else float("nan"),
        "fps_min": float(np.min(fps_arr)) if fps_arr.size else float("nan"),
        "fps_max": float(np.max(fps_arr)) if fps_arr.size else float("nan"),
        "n_loci_cache": len(cache),
        "errors": errors[:50],
        "n_errors_truncated": max(0, len(errors) - 50),
    }
    return move_rows, immobile_rows, summary


def discover_paramscan_models(ensemble_root: Path | str) -> list[str]:
    """Sorted ``paramscan_*`` folder names that contain ``results.h5``."""
    root = Path(ensemble_root)
    names: list[str] = []
    for p in sorted(root.glob("paramscan_*")):
        if p.is_dir() and (p / "results.h5").is_file():
            names.append(p.name)
    return names
