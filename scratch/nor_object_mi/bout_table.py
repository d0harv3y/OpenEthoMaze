"""Build syllable-bout rows with bout-mean object distances."""

from __future__ import annotations

from typing import Iterator, Mapping, Sequence
from collections import defaultdict

import h5py
import numpy as np

from maze.kpms.behavior_ethogram.bout_scalars import syllable_runs

from .fam_nvl import fam_nvl_map_for_session
from .join_keys import JoinedSession
from .pseudo_loci import loci_for_animal_phase, match_centers_to_loci
from .spot_xy import (
    all_object_distances_m,
    dist_to_center_m,
    nearest_distance_m,
    object_centers_px,
    role_distances_m,
    spot_xy_m,
)
from .syllable_cleanup import maybe_absorb_short_bouts

BOUT_FIELDS: tuple[str, ...] = (
    "kpms_key",
    "trial_key",
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
    "bout_mean_dist_fam_m",
    "bout_mean_dist_nvl_m",
    "bout_mean_dist_obj_a_m",
    "bout_mean_dist_obj_b_m",
    "bout_mean_dist_locus_a_m",
    "bout_mean_dist_locus_b_m",
    "bout_mean_dist_any_m",
    "obj_a_id",
    "obj_b_id",
    "dist_any_source",
    "locus_label_policy",
    "role_at_locus_a",
    "role_at_locus_b",
    "nvl_nearest_hist_locus",
)

# Conditions that contribute real object centers to shared distance bins.
EDGE_FIT_CONDITIONS: frozenset[str] = frozenset({"novel_obj", "identical_obj"})


def _align_syll_dists(
    syll: np.ndarray,
    dists: Sequence[np.ndarray],
) -> tuple[np.ndarray, list[np.ndarray]]:
    n = int(syll.shape[0])
    for d in dists:
        n = min(n, int(d.shape[0]))
    return syll[:n], [d[:n] for d in dists]


def _bout_mean(arr: np.ndarray, start: int, end: int) -> float:
    sl = arr[start:end]
    finite = sl[np.isfinite(sl)]
    if finite.size == 0:
        return float("nan")
    return float(np.mean(finite))


def build_bout_rows(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    sessions: Sequence[JoinedSession],
    *,
    condition_layers: Sequence[str] = ("novel_obj", "identical_obj"),
    loci_cache: Mapping[tuple[str, str], np.ndarray] | None = None,
    min_bout_frames: int | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Collapse kpMS syllables to bouts; attach bout-mean spot→object distances.

    ``novel_obj``: role-labeled fam/nvl distances (+ sorted obj_a/obj_b).
    ``identical_obj``: sorted obj_a/obj_b (fam/nvl left NaN).

    Spatial channels ``bout_mean_dist_locus_{a,b}_m`` are distances to **fixed
    historical** animal×phase 2-means loci (lower-x = A), not to session object
    centers. On ``novel_obj``, ``nvl_nearest_hist_locus`` tags which historical
    locus is nearer the session novel-object center.
    """
    rows: list[dict[str, object]] = []
    n_skip_cond = 0
    n_skip_map = 0
    n_skip_loci = 0
    n_skip_err = 0
    n_novel = 0
    n_identical = 0
    errors: list[dict[str, str]] = []
    wanted = set(condition_layers)
    cache: dict[tuple[str, str], np.ndarray] = dict(loci_cache or {})
    locus_policy = "hist_2means_x_order_fixed"

    for js in sessions:
        if js.condition_layer not in wanted:
            n_skip_cond += 1
            continue
        try:
            sg = nor_h5[js.animal_id][js.raw_session]
            syll = maybe_absorb_short_bouts(
                kpms_h5[js.kpms_key]["syllable"][()],
                min_bout_frames,
            )
            obj_keys, obj_dists, _valid = all_object_distances_m(sg)
            if len(obj_keys) < 2:
                n_skip_err += 1
                errors.append(
                    {
                        "animal_id": js.animal_id,
                        "raw_session": js.raw_session,
                        "reason": f"need >=2 objects, got {len(obj_keys)}",
                    }
                )
                continue

            d_a, d_b = obj_dists[0], obj_dists[1]
            obj_a_id, obj_b_id = obj_keys[0], obj_keys[1]
            d_fam = np.full(d_a.shape, np.nan, dtype=np.float64)
            d_nvl = np.full(d_a.shape, np.nan, dtype=np.float64)

            loci_key = (js.animal_id, js.phase_layer)
            if loci_key not in cache:
                loci = loci_for_animal_phase(nor_h5, js.animal_id, js.phase_layer)
                if loci is None:
                    n_skip_loci += 1
                    errors.append(
                        {
                            "animal_id": js.animal_id,
                            "raw_session": js.raw_session,
                            "reason": "spatial_loci_unavailable",
                        }
                    )
                    continue
                cache[loci_key] = loci
            loci = cache[loci_key]

            centers = object_centers_px(sg)
            x_m, y_m, valid, ppm = spot_xy_m(sg)
            # Fixed historical means (not session centers)
            d_locus_a = dist_to_center_m(x_m, y_m, valid, loci[0], ppm)
            d_locus_b = dist_to_center_m(x_m, y_m, valid, loci[1], ppm)
            role_at_a = ""
            role_at_b = ""
            nvl_nearest = ""

            if js.condition_layer == "novel_obj":
                role_map = fam_nvl_map_for_session(nor_h5, js.animal_id, js.raw_session)
                if not role_map:
                    n_skip_map += 1
                    errors.append(
                        {
                            "animal_id": js.animal_id,
                            "raw_session": js.raw_session,
                            "reason": "fam_nvl_map_failed",
                        }
                    )
                    continue
                d_fam, d_nvl, _ = role_distances_m(sg, role_map)
                nvl_key = next(k for k, v in role_map.items() if v == "nvl")
                nvl_c = centers[nvl_key]
                # Which historical locus is nearer the session nvl center
                d_nvl_a = float(np.sum((nvl_c - loci[0]) ** 2))
                d_nvl_b = float(np.sum((nvl_c - loci[1]) ** 2))
                if d_nvl_a <= d_nvl_b:
                    nvl_nearest = "a"
                    role_at_a, role_at_b = "nvl", "fam"
                else:
                    nvl_nearest = "b"
                    role_at_a, role_at_b = "fam", "nvl"
                n_novel += 1
            elif js.condition_layer == "identical_obj":
                n_identical += 1
            else:
                n_skip_cond += 1
                continue

            syll, aligned = _align_syll_dists(
                syll, [d_fam, d_nvl, d_a, d_b, d_locus_a, d_locus_b]
            )
            d_fam, d_nvl, d_a, d_b, d_locus_a, d_locus_b = aligned
            runs = syllable_runs(syll)
            trial_key = f"{js.animal_id}/{js.raw_session}"
            for bout_index, (sid, start, end) in enumerate(runs):
                rows.append(
                    {
                        "kpms_key": js.kpms_key,
                        "trial_key": trial_key,
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
                        "bout_frames": int(end - start),
                        "bout_mean_dist_fam_m": _bout_mean(d_fam, start, end),
                        "bout_mean_dist_nvl_m": _bout_mean(d_nvl, start, end),
                        "bout_mean_dist_obj_a_m": _bout_mean(d_a, start, end),
                        "bout_mean_dist_obj_b_m": _bout_mean(d_b, start, end),
                        "bout_mean_dist_locus_a_m": _bout_mean(d_locus_a, start, end),
                        "bout_mean_dist_locus_b_m": _bout_mean(d_locus_b, start, end),
                        "bout_mean_dist_any_m": _bout_mean(np.minimum(d_a, d_b), start, end),
                        "obj_a_id": obj_a_id,
                        "obj_b_id": obj_b_id,
                        "dist_any_source": "real_objects",
                        "locus_label_policy": locus_policy,
                        "role_at_locus_a": role_at_a,
                        "role_at_locus_b": role_at_b,
                        "nvl_nearest_hist_locus": nvl_nearest,
                    }
                )
        except Exception as exc:  # noqa: BLE001 — scratch pilot: record and continue
            n_skip_err += 1
            errors.append(
                {
                    "animal_id": js.animal_id,
                    "raw_session": js.raw_session,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )

    summary = {
        "n_bout_rows": len(rows),
        "n_sessions_novel_obj": n_novel,
        "n_sessions_identical_obj": n_identical,
        "n_skip_condition": n_skip_cond,
        "n_skip_fam_nvl_map": n_skip_map,
        "n_skip_spatial_loci": n_skip_loci,
        "n_skip_error": n_skip_err,
        "n_loci_cache": len(cache),
        "locus_label_policy": locus_policy,
        "min_bout_frames": min_bout_frames,
        "syllable_cleanup": (
            f"absorb_short_bouts<{min_bout_frames}"
            if min_bout_frames is not None and int(min_bout_frames) > 1
            else "none"
        ),
        "errors": errors[:50],
        "n_errors_truncated": max(0, len(errors) - 50),
    }
    return rows, summary


def build_presence_bout_rows(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    sessions: Sequence[JoinedSession],
    *,
    loci_cache: Mapping[tuple[str, str], np.ndarray] | None = None,
    min_bout_frames: int | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Bouts for object-presence question: ``identical_obj`` vs ``no_obj``.

    Distance fields:
    - ``bout_mean_dist_any_m``: bout-mean nearest-locus distance
    - ``bout_mean_dist_locus_{a,b}_m``: distances to spatially labeled loci
      (animal×phase 2-means, lower-x = A). On ``identical_obj``, each real
      object center is matched to A/B; on ``no_obj``, targets are the
      pseudo-loci themselves.
    - ``bout_mean_dist_obj_{a,b}_m``: distances to sorted ``object_*`` keys
      (identical only; NaN on no_obj) — legacy / diagnostic
    """
    rows: list[dict[str, object]] = []
    n_identical = 0
    n_no = 0
    n_skip_cond = 0
    n_skip_loci = 0
    n_skip_err = 0
    errors: list[dict[str, str]] = []
    cache: dict[tuple[str, str], np.ndarray] = dict(loci_cache or {})
    locus_policy = "spatial_2means_x_order"

    for js in sessions:
        if js.condition_layer not in {"identical_obj", "no_obj"}:
            n_skip_cond += 1
            continue
        try:
            sg = nor_h5[js.animal_id][js.raw_session]
            syll = maybe_absorb_short_bouts(
                kpms_h5[js.kpms_key]["syllable"][()],
                min_bout_frames,
            )

            key = (js.animal_id, js.phase_layer)
            if key not in cache:
                loci = loci_for_animal_phase(nor_h5, js.animal_id, js.phase_layer)
                if loci is None:
                    n_skip_loci += 1
                    errors.append(
                        {
                            "animal_id": js.animal_id,
                            "raw_session": js.raw_session,
                            "reason": "spatial_loci_unavailable",
                        }
                    )
                    continue
                cache[key] = loci
            loci = cache[key]

            x_m, y_m, valid, ppm = spot_xy_m(sg)
            d_locus_a = dist_to_center_m(x_m, y_m, valid, loci[0], ppm)
            d_locus_b = dist_to_center_m(x_m, y_m, valid, loci[1], ppm)

            if js.condition_layer == "identical_obj":
                centers = object_centers_px(sg)
                if len(centers) < 2:
                    n_skip_err += 1
                    errors.append(
                        {
                            "animal_id": js.animal_id,
                            "raw_session": js.raw_session,
                            "reason": "need >=2 object centers on identical_obj",
                        }
                    )
                    continue
                keys = sorted(centers)
                obj_a_id, obj_b_id = keys[0], keys[1]
                d_obj_a = dist_to_center_m(x_m, y_m, valid, centers[keys[0]], ppm)
                d_obj_b = dist_to_center_m(x_m, y_m, valid, centers[keys[1]], ppm)
                # Spatial labels: match real centers onto animal×phase loci A/B
                c_a, c_b = match_centers_to_loci([centers[k] for k in keys], loci)
                d_locus_a = dist_to_center_m(x_m, y_m, valid, c_a, ppm)
                d_locus_b = dist_to_center_m(x_m, y_m, valid, c_b, ppm)
                d_any, _ = nearest_distance_m(sg, [c_a, c_b])
                source = "real_objects"
                n_identical += 1
            else:
                obj_a_id, obj_b_id = "pseudo_locus_0", "pseudo_locus_1"
                d_obj_a = np.full(x_m.shape, np.nan, dtype=np.float64)
                d_obj_b = np.full(x_m.shape, np.nan, dtype=np.float64)
                # d_locus_* already aimed at pseudo-loci
                d_any, _ = nearest_distance_m(sg, [loci[0], loci[1]])
                source = "pseudo_loci"
                n_no += 1

            syll, aligned = _align_syll_dists(
                syll, [d_any, d_locus_a, d_locus_b, d_obj_a, d_obj_b]
            )
            d_any, d_locus_a, d_locus_b, d_obj_a, d_obj_b = aligned

            runs = syllable_runs(syll)
            trial_key = f"{js.animal_id}/{js.raw_session}"
            for bout_index, (sid, start, end) in enumerate(runs):
                rows.append(
                    {
                        "kpms_key": js.kpms_key,
                        "trial_key": trial_key,
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
                        "bout_frames": int(end - start),
                        "bout_mean_dist_fam_m": float("nan"),
                        "bout_mean_dist_nvl_m": float("nan"),
                        "bout_mean_dist_obj_a_m": _bout_mean(d_obj_a, start, end),
                        "bout_mean_dist_obj_b_m": _bout_mean(d_obj_b, start, end),
                        "bout_mean_dist_locus_a_m": _bout_mean(d_locus_a, start, end),
                        "bout_mean_dist_locus_b_m": _bout_mean(d_locus_b, start, end),
                        "bout_mean_dist_any_m": _bout_mean(d_any, start, end),
                        "obj_a_id": obj_a_id,
                        "obj_b_id": obj_b_id,
                        "dist_any_source": source,
                        "locus_label_policy": locus_policy,
                        "role_at_locus_a": "",
                        "role_at_locus_b": "",
                        "nvl_nearest_hist_locus": "",
                    }
                )
        except Exception as exc:  # noqa: BLE001 — scratch pilot: record and continue
            n_skip_err += 1
            errors.append(
                {
                    "animal_id": js.animal_id,
                    "raw_session": js.raw_session,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )

    summary = {
        "n_bout_rows": len(rows),
        "n_sessions_identical_obj": n_identical,
        "n_sessions_no_obj": n_no,
        "n_skip_condition": n_skip_cond,
        "n_skip_spatial_loci": n_skip_loci,
        "n_skip_error": n_skip_err,
        "n_loci_cache": len(cache),
        "locus_label_policy": locus_policy,
        "min_bout_frames": min_bout_frames,
        "syllable_cleanup": (
            f"absorb_short_bouts<{min_bout_frames}"
            if min_bout_frames is not None and int(min_bout_frames) > 1
            else "none"
        ),
        "errors": errors[:50],
        "n_errors_truncated": max(0, len(errors) - 50),
    }
    return rows, summary


def build_ladder_bout_rows(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    sessions: Sequence[JoinedSession],
    *,
    loci_cache: Mapping[tuple[str, str], np.ndarray] | None = None,
    min_bout_frames: int | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Bouts for condition ladder: ``no_obj``, ``identical_obj``, ``novel_obj``.

    ``bout_mean_dist_locus_{a,b}_m`` = distance to **fixed** animal×phase historical
    means (all three conditions). On ``novel_obj``, also fill fam/nvl role distances
    and ``nvl_nearest_hist_locus``.
    """
    rows: list[dict[str, object]] = []
    n_by_cond: dict[str, int] = defaultdict(int)
    n_skip_cond = 0
    n_skip_map = 0
    n_skip_loci = 0
    n_skip_err = 0
    errors: list[dict[str, str]] = []
    cache: dict[tuple[str, str], np.ndarray] = dict(loci_cache or {})
    locus_policy = "hist_2means_x_order_fixed"
    wanted = {"no_obj", "identical_obj", "novel_obj"}

    for js in sessions:
        if js.condition_layer not in wanted:
            n_skip_cond += 1
            continue
        try:
            sg = nor_h5[js.animal_id][js.raw_session]
            syll = maybe_absorb_short_bouts(
                kpms_h5[js.kpms_key]["syllable"][()],
                min_bout_frames,
            )

            key = (js.animal_id, js.phase_layer)
            if key not in cache:
                loci = loci_for_animal_phase(nor_h5, js.animal_id, js.phase_layer)
                if loci is None:
                    n_skip_loci += 1
                    errors.append(
                        {
                            "animal_id": js.animal_id,
                            "raw_session": js.raw_session,
                            "reason": "spatial_loci_unavailable",
                        }
                    )
                    continue
                cache[key] = loci
            loci = cache[key]

            x_m, y_m, valid, ppm = spot_xy_m(sg)
            d_locus_a = dist_to_center_m(x_m, y_m, valid, loci[0], ppm)
            d_locus_b = dist_to_center_m(x_m, y_m, valid, loci[1], ppm)
            d_fam = np.full(x_m.shape, np.nan, dtype=np.float64)
            d_nvl = np.full(x_m.shape, np.nan, dtype=np.float64)
            d_obj_a = np.full(x_m.shape, np.nan, dtype=np.float64)
            d_obj_b = np.full(x_m.shape, np.nan, dtype=np.float64)
            obj_a_id = obj_b_id = ""
            nvl_nearest = ""
            role_at_a = role_at_b = ""
            source = "hist_loci"

            if js.condition_layer in {"identical_obj", "novel_obj"}:
                centers = object_centers_px(sg)
                if len(centers) < 2:
                    n_skip_err += 1
                    errors.append(
                        {
                            "animal_id": js.animal_id,
                            "raw_session": js.raw_session,
                            "reason": "need >=2 object centers",
                        }
                    )
                    continue
                keys = sorted(centers)
                obj_a_id, obj_b_id = keys[0], keys[1]
                d_obj_a = dist_to_center_m(x_m, y_m, valid, centers[keys[0]], ppm)
                d_obj_b = dist_to_center_m(x_m, y_m, valid, centers[keys[1]], ppm)
                d_any, _ = nearest_distance_m(sg, [centers[keys[0]], centers[keys[1]]])
                source = "real_objects"
            else:
                d_any, _ = nearest_distance_m(sg, [loci[0], loci[1]])
                obj_a_id, obj_b_id = "pseudo_locus_0", "pseudo_locus_1"
                source = "pseudo_loci"

            if js.condition_layer == "novel_obj":
                role_map = fam_nvl_map_for_session(nor_h5, js.animal_id, js.raw_session)
                if not role_map:
                    n_skip_map += 1
                    errors.append(
                        {
                            "animal_id": js.animal_id,
                            "raw_session": js.raw_session,
                            "reason": "fam_nvl_map_failed",
                        }
                    )
                    continue
                d_fam, d_nvl, _ = role_distances_m(sg, role_map)
                nvl_key = next(k for k, v in role_map.items() if v == "nvl")
                nvl_c = object_centers_px(sg)[nvl_key]
                d_nvl_a = float(np.sum((nvl_c - loci[0]) ** 2))
                d_nvl_b = float(np.sum((nvl_c - loci[1]) ** 2))
                if d_nvl_a <= d_nvl_b:
                    nvl_nearest = "a"
                    role_at_a, role_at_b = "nvl", "fam"
                else:
                    nvl_nearest = "b"
                    role_at_a, role_at_b = "fam", "nvl"

            n_by_cond[js.condition_layer] += 1
            syll, aligned = _align_syll_dists(
                syll, [d_any, d_locus_a, d_locus_b, d_fam, d_nvl, d_obj_a, d_obj_b]
            )
            d_any, d_locus_a, d_locus_b, d_fam, d_nvl, d_obj_a, d_obj_b = aligned
            runs = syllable_runs(syll)
            trial_key = f"{js.animal_id}/{js.raw_session}"
            for bout_index, (sid, start, end) in enumerate(runs):
                rows.append(
                    {
                        "kpms_key": js.kpms_key,
                        "trial_key": trial_key,
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
                        "bout_frames": int(end - start),
                        "bout_mean_dist_fam_m": _bout_mean(d_fam, start, end),
                        "bout_mean_dist_nvl_m": _bout_mean(d_nvl, start, end),
                        "bout_mean_dist_obj_a_m": _bout_mean(d_obj_a, start, end),
                        "bout_mean_dist_obj_b_m": _bout_mean(d_obj_b, start, end),
                        "bout_mean_dist_locus_a_m": _bout_mean(d_locus_a, start, end),
                        "bout_mean_dist_locus_b_m": _bout_mean(d_locus_b, start, end),
                        "bout_mean_dist_any_m": _bout_mean(d_any, start, end),
                        "obj_a_id": obj_a_id,
                        "obj_b_id": obj_b_id,
                        "dist_any_source": source,
                        "locus_label_policy": locus_policy,
                        "role_at_locus_a": role_at_a,
                        "role_at_locus_b": role_at_b,
                        "nvl_nearest_hist_locus": nvl_nearest,
                    }
                )
        except Exception as exc:  # noqa: BLE001 — scratch pilot: record and continue
            n_skip_err += 1
            errors.append(
                {
                    "animal_id": js.animal_id,
                    "raw_session": js.raw_session,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )

    summary = {
        "n_bout_rows": len(rows),
        "n_sessions_by_condition": dict(n_by_cond),
        "n_skip_condition": n_skip_cond,
        "n_skip_fam_nvl_map": n_skip_map,
        "n_skip_spatial_loci": n_skip_loci,
        "n_skip_error": n_skip_err,
        "n_loci_cache": len(cache),
        "locus_label_policy": locus_policy,
        "min_bout_frames": min_bout_frames,
        "syllable_cleanup": (
            f"absorb_short_bouts<{min_bout_frames}"
            if min_bout_frames is not None and int(min_bout_frames) > 1
            else "none"
        ),
        "errors": errors[:50],
        "n_errors_truncated": max(0, len(errors) - 50),
    }
    return rows, summary


def iter_animal_ids(rows: Sequence[dict[str, object]]) -> Iterator[str]:
    seen: set[str] = set()
    for row in rows:
        aid = str(row["animal_id"])
        if aid not in seen:
            seen.add(aid)
            yield aid
