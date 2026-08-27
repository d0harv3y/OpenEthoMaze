"""Occupancy MI for dist_fam / dist_nvl and novelty Δ by treatment."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal, Mapping, Sequence

import numpy as np
from scipy import stats

from maze.kpms.behavior_ethogram.stimulus_mi import (
    assign_bins,
    global_quantile_bin_edges,
    occupancy_mi,
)

StimVar = Literal["dist_fam", "dist_nvl"]
STIM_VARS: tuple[StimVar, ...] = ("dist_fam", "dist_nvl")
_FIELD: dict[StimVar, str] = {
    "dist_fam": "bout_mean_dist_fam_m",
    "dist_nvl": "bout_mean_dist_nvl_m",
}


def _json_edges_to_array(raw: Sequence[object]) -> np.ndarray:
    edges = np.asarray(
        [-np.inf if (v is None or v == "-inf") else (np.inf if v == "inf" else float(v)) for v in raw],
        dtype=np.float64,
    )
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def edges_from_json(payload: Mapping[str, object], stim: StimVar | None = None) -> np.ndarray:
    """Load shared object-distance edges (canonical key ``dist``).

    Legacy payloads with separate ``dist_fam`` / ``dist_nvl`` still load; if both
    exist they must match when ``stim`` is omitted.
    """
    if "dist" in payload:
        return _json_edges_to_array(list(payload["dist"]))  # type: ignore[arg-type]
    if stim is not None and stim in payload:
        return _json_edges_to_array(list(payload[stim]))  # type: ignore[arg-type]
    if "dist_fam" in payload and "dist_nvl" in payload:
        fam = _json_edges_to_array(list(payload["dist_fam"]))  # type: ignore[arg-type]
        nvl = _json_edges_to_array(list(payload["dist_nvl"]))  # type: ignore[arg-type]
        if fam.shape != nvl.shape or not np.allclose(fam[1:-1], nvl[1:-1], equal_nan=True):
            raise ValueError("legacy bin_edges.json has mismatched dist_fam / dist_nvl; refit shared dist")
        return fam
    raise KeyError("bin_edges payload needs 'dist' (or legacy dist_fam/dist_nvl)")


_EDGE_FIT_CONDITIONS: frozenset[str] = frozenset({"novel_obj", "identical_obj"})


def pool_any_object_bout_distances(rows: Sequence[Mapping[str, object]]) -> list[float]:
    """Finite bout-mean distances to any real object (novel + identical; skip no_obj).

    Each two-object bout contributes exactly two distances:
    - ``novel_obj`` → fam + nvl (role-labeled)
    - ``identical_obj`` → obj_a + obj_b (sorted object ids)
    """
    vals: list[float] = []
    for r in rows:
        cond = str(r.get("condition_layer", ""))
        if cond == "novel_obj":
            fields = ("bout_mean_dist_fam_m", "bout_mean_dist_nvl_m")
        elif cond == "identical_obj":
            fields = ("bout_mean_dist_obj_a_m", "bout_mean_dist_obj_b_m")
        else:
            continue
        for field in fields:
            raw = r.get(field, "")
            if raw is None or raw == "":
                continue
            val = float(raw)
            if np.isfinite(val):
                vals.append(val)
    return vals


def fit_shared_dist_bin_edges(
    rows: Sequence[Mapping[str, object]],
    *,
    n_bins: int = 5,
) -> tuple[np.ndarray, dict[str, object]]:
    """One quantile edge set for all object-distance channels."""
    vals = pool_any_object_bout_distances(rows)
    edges = global_quantile_bin_edges(vals, n_bins)
    json_edges = [None if not np.isfinite(e) else float(e) for e in edges]
    by_cond: dict[str, int] = {}
    for r in rows:
        cond = str(r.get("condition_layer", ""))
        if cond in _EDGE_FIT_CONDITIONS:
            by_cond[cond] = by_cond.get(cond, 0) + 1
    payload: dict[str, object] = {
        "dist": json_edges,
        "dist_fam": json_edges,
        "dist_nvl": json_edges,
        "fit": {
            "policy": "shared_any_object",
            "source_fields_by_condition": {
                "novel_obj": ["bout_mean_dist_fam_m", "bout_mean_dist_nvl_m"],
                "identical_obj": ["bout_mean_dist_obj_a_m", "bout_mean_dist_obj_b_m"],
            },
            "condition_layers": sorted(_EDGE_FIT_CONDITIONS),
            "n_bout_rows_by_condition": by_cond,
            "n_bins": n_bins,
            "n_values": len(vals),
            "excluded": ["no_obj (no pseudo-target yet; two historical loci later)"],
        },
    }
    return edges, payload


def _circular_shift_amount(size: int, rng: np.random.Generator) -> int:
    if size <= 1:
        return 0
    return int(rng.integers(1, size))


def _null_p(observed: float, nulls: np.ndarray) -> float:
    if nulls.size == 0:
        return float("nan")
    return float((np.sum(nulls >= observed) + 1) / (nulls.size + 1))


def _streams_for_animal(
    rows: Sequence[Mapping[str, object]],
    *,
    animal_id: str,
    stim: StimVar,
    edges: np.ndarray,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    return _streams_for_animal_field(
        rows, animal_id=animal_id, field=_FIELD[stim], edges=edges
    )


def _streams_for_animal_field(
    rows: Sequence[Mapping[str, object]],
    *,
    animal_id: str,
    field: str,
    edges: np.ndarray,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    by_trial: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if str(row["animal_id"]) != animal_id:
            continue
        if str(row.get("condition_layer", "")) != "novel_obj":
            continue
        val = float(row[field])
        if not np.isfinite(val):
            continue
        by_trial[str(row["trial_key"])].append(row)

    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for trial, trows in by_trial.items():
        trows = sorted(trows, key=lambda r: int(r["bout_index"]))
        syll = np.asarray([int(r["raw_syllable_id"]) for r in trows], dtype=np.int64)
        stim_vals = np.asarray([float(r[field]) for r in trows], dtype=np.float64)
        stim_bin = assign_bins(stim_vals, edges)
        out[trial] = (syll, stim_bin)
    return out


def _pooled_occupancy(streams: dict[str, tuple[np.ndarray, np.ndarray]]) -> tuple[float, float, float, float, int]:
    syll_parts: list[np.ndarray] = []
    stim_parts: list[np.ndarray] = []
    for syll, stim in streams.values():
        mask = stim >= 0
        if not np.any(mask):
            continue
        syll_parts.append(syll[mask])
        stim_parts.append(stim[mask])
    if not syll_parts:
        return 0.0, 0.0, 0.0, 0.0, 0
    return occupancy_mi(np.concatenate(syll_parts), np.concatenate(stim_parts))


def _null_circ_mean_p(
    streams: dict[str, tuple[np.ndarray, np.ndarray]],
    *,
    observed_mm: float,
    n_perm: int,
    rng: np.random.Generator,
) -> tuple[float, float]:
    nulls: list[float] = []
    for _ in range(n_perm):
        shifted: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for trial, (syll, stim) in streams.items():
            if stim.size == 0:
                continue
            k = _circular_shift_amount(int(stim.size), rng)
            shifted[trial] = (syll, np.roll(stim, k))
        _, mm, _, _, _ = _pooled_occupancy(shifted)
        nulls.append(mm)
    arr = np.asarray(nulls, dtype=np.float64)
    return float(np.mean(arr)), _null_p(observed_mm, arr)


def compute_pilot_mi(
    rows: Sequence[Mapping[str, object]],
    *,
    n_bins: int = 5,
    n_perm: int = 200,
    seed: int = 42,
    bin_edges_payload: Mapping[str, object] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Return mi_rows, delta_rows, group_tests, bin_edges_json."""
    if bin_edges_payload is None:
        shared_edges, bin_edges_payload = fit_shared_dist_bin_edges(rows, n_bins=n_bins)
    else:
        shared_edges = edges_from_json(bin_edges_payload)
    edge_arrays: dict[StimVar, np.ndarray] = {stim: shared_edges for stim in STIM_VARS}

    animals = sorted({str(r["animal_id"]) for r in rows})
    meta_by_animal: dict[str, Mapping[str, object]] = {}
    for r in rows:
        meta_by_animal.setdefault(str(r["animal_id"]), r)

    rng = np.random.default_rng(seed)
    mi_rows: list[dict[str, object]] = []

    for aid in animals:
        meta = meta_by_animal[aid]
        for stim in STIM_VARS:
            streams = _streams_for_animal(rows, animal_id=aid, stim=stim, edges=edge_arrays[stim])
            if not streams:
                continue
            mi_raw, mi_mm, h_syll, h_stim, n_bouts = _pooled_occupancy(streams)
            if n_bouts == 0:
                continue
            null_mean, null_p = _null_circ_mean_p(
                streams, observed_mm=mi_mm, n_perm=n_perm, rng=rng
            )
            excess = float(mi_mm - null_mean)
            mi_rows.append(
                {
                    "animal_id": aid,
                    "sex": meta["sex"],
                    "tx": meta["tx"],
                    "cohort": meta["cohort"],
                    "phase_layer": meta["phase_layer"],
                    "stim_var": stim,
                    "mi_type": "occupancy",
                    "n_bouts": n_bouts,
                    "H_stim": h_stim,
                    "H_syll": h_syll,
                    "mi_raw": mi_raw,
                    "mi_mm": mi_mm,
                    "null_circ_mean": null_mean,
                    "null_circ_p": null_p,
                    "excess": excess,
                }
            )

    # Novelty contrast Δ
    by_animal: dict[str, dict[str, Mapping[str, object]]] = defaultdict(dict)
    for row in mi_rows:
        by_animal[str(row["animal_id"])][str(row["stim_var"])] = row

    delta_rows: list[dict[str, object]] = []
    for aid, stim_map in sorted(by_animal.items()):
        if "dist_fam" not in stim_map or "dist_nvl" not in stim_map:
            continue
        fam = stim_map["dist_fam"]
        nvl = stim_map["dist_nvl"]
        delta_rows.append(
            {
                "animal_id": aid,
                "sex": fam["sex"],
                "tx": fam["tx"],
                "cohort": fam["cohort"],
                "phase_layer": fam["phase_layer"],
                "excess_fam": fam["excess"],
                "excess_nvl": nvl["excess"],
                "delta_excess_nvl_minus_fam": float(nvl["excess"]) - float(fam["excess"]),  # type: ignore[arg-type]
                "mi_mm_fam": fam["mi_mm"],
                "mi_mm_nvl": nvl["mi_mm"],
                "n_bouts_fam": fam["n_bouts"],
                "n_bouts_nvl": nvl["n_bouts"],
            }
        )

    group_tests = _group_tests_delta(delta_rows)
    return mi_rows, delta_rows, group_tests, dict(bin_edges_payload)


def _factor_tests_on_subset(
    subset: Sequence[Mapping[str, object]],
    *,
    factor: str,
    sex_stratum: str,
) -> list[dict[str, object]]:
    """Kruskal / Mann–Whitney on Δ for one factor within a sex stratum."""
    out: list[dict[str, object]] = []
    by_level: dict[str, list[float]] = defaultdict(list)
    for row in subset:
        level = str(row.get(factor, "") or "")
        if not level:
            continue
        val = float(row["delta_excess_nvl_minus_fam"])
        if np.isfinite(val):
            by_level[level].append(val)
    levels = sorted(by_level)
    if len(levels) < 2:
        return out

    def _row(
        *,
        level_a: str,
        level_b: str,
        n_a: int,
        n_b: int,
        median_a: float,
        median_b: float,
        stat: float,
        p: float,
        test: str,
    ) -> dict[str, object]:
        return {
            "sex_stratum": sex_stratum,
            "factor": factor,
            "level_a": level_a,
            "level_b": level_b,
            "n_a": n_a,
            "n_b": n_b,
            "median_a": median_a,
            "median_b": median_b,
            "stat": stat,
            "p": p,
            "test": test,
            "metric": "delta_excess_nvl_minus_fam",
        }

    if len(levels) == 2:
        a, b = levels
        va, vb = by_level[a], by_level[b]
        stat, p = stats.mannwhitneyu(va, vb, alternative="two-sided")
        out.append(
            _row(
                level_a=a,
                level_b=b,
                n_a=len(va),
                n_b=len(vb),
                median_a=float(np.median(va)),
                median_b=float(np.median(vb)),
                stat=float(stat),
                p=float(p),
                test="mannwhitneyu",
            )
        )
        return out

    samples = [by_level[level] for level in levels]
    stat, p = stats.kruskal(*samples)
    all_vals = [v for s in samples for v in s]
    out.append(
        _row(
            level_a="|".join(levels),
            level_b="",
            n_a=len(all_vals),
            n_b=0,
            median_a=float(np.median(all_vals)),
            median_b=float("nan"),
            stat=float(stat),
            p=float(p),
            test="kruskal",
        )
    )
    if factor == "tx":
        for i, a in enumerate(levels):
            for b in levels[i + 1 :]:
                va, vb = by_level[a], by_level[b]
                if len(va) == 0 or len(vb) == 0:
                    continue
                stat_pw, p_pw = stats.mannwhitneyu(va, vb, alternative="two-sided")
                out.append(
                    _row(
                        level_a=a,
                        level_b=b,
                        n_a=len(va),
                        n_b=len(vb),
                        median_a=float(np.median(va)),
                        median_b=float(np.median(vb)),
                        stat=float(stat_pw),
                        p=float(p_pw),
                        test="mannwhitneyu_pairwise",
                    )
                )
    return out


def _group_tests_delta(delta_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Pooled and sex-stratified group tests on novelty Δ."""
    out: list[dict[str, object]] = []
    # Pooled (sexes combined)
    out.extend(_factor_tests_on_subset(delta_rows, factor="tx", sex_stratum="all"))
    out.extend(_factor_tests_on_subset(delta_rows, factor="sex", sex_stratum="all"))
    # Within each sex: treatment contrasts
    sexes = sorted({str(r.get("sex", "") or "") for r in delta_rows if str(r.get("sex", "") or "")})
    for sex in sexes:
        subset = [r for r in delta_rows if str(r.get("sex", "")) == sex]
        out.extend(_factor_tests_on_subset(subset, factor="tx", sex_stratum=sex))
    # Within each tx: sex contrast (explicit 2×3 cell structure)
    txs = sorted({str(r.get("tx", "") or "") for r in delta_rows if str(r.get("tx", "") or "")})
    for tx in txs:
        subset = [r for r in delta_rows if str(r.get("tx", "")) == tx]
        # reuse sex_stratum field to label the tx cell; factor remains sex
        cell_tests = _factor_tests_on_subset(subset, factor="sex", sex_stratum=f"tx={tx}")
        out.extend(cell_tests)
    return out


NOVELTY_LOCUS_STIMS: tuple[tuple[str, str], ...] = (
    ("dist_fam", "bout_mean_dist_fam_m"),
    ("dist_nvl", "bout_mean_dist_nvl_m"),
    ("dist_locus_a", "bout_mean_dist_locus_a_m"),
    ("dist_locus_b", "bout_mean_dist_locus_b_m"),
)


def compute_novelty_loci_mi(
    rows: Sequence[Mapping[str, object]],
    *,
    n_bins: int = 5,
    n_perm: int = 200,
    seed: int = 42,
    bin_edges_payload: Mapping[str, object] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Novelty fam/nvl MI plus fixed historical locus A/B on ``novel_obj``.

    Contrasts per animal:
    - ``delta_excess_nvl_minus_fam`` (role; session object centers)
    - ``delta_excess_locus_b_minus_a`` (spatial; fixed hist means)
    - ``delta_excess_nvl_side_minus_other`` (hist locus nearer session nvl − other)
    """
    if bin_edges_payload is None:
        shared_edges, bin_edges_payload = fit_shared_dist_bin_edges(rows, n_bins=n_bins)
    else:
        shared_edges = edges_from_json(bin_edges_payload)

    animals = sorted({str(r["animal_id"]) for r in rows})
    meta_by_animal: dict[str, Mapping[str, object]] = {}
    for r in rows:
        meta_by_animal.setdefault(str(r["animal_id"]), r)

    rng = np.random.default_rng(seed)
    mi_rows: list[dict[str, object]] = []
    for aid in animals:
        meta = meta_by_animal[aid]
        for stim_var, field in NOVELTY_LOCUS_STIMS:
            streams = _streams_for_animal_field(
                rows, animal_id=aid, field=field, edges=shared_edges
            )
            if not streams:
                continue
            mi_raw, mi_mm, h_syll, h_stim, n_bouts = _pooled_occupancy(streams)
            if n_bouts == 0:
                continue
            null_mean, null_p = _null_circ_mean_p(
                streams, observed_mm=mi_mm, n_perm=n_perm, rng=rng
            )
            mi_rows.append(
                {
                    "animal_id": aid,
                    "sex": meta["sex"],
                    "tx": meta["tx"],
                    "cohort": meta["cohort"],
                    "phase_layer": meta["phase_layer"],
                    "stim_var": stim_var,
                    "mi_type": "occupancy",
                    "n_bouts": n_bouts,
                    "H_stim": h_stim,
                    "H_syll": h_syll,
                    "mi_raw": mi_raw,
                    "mi_mm": mi_mm,
                    "null_circ_mean": null_mean,
                    "null_circ_p": null_p,
                    "excess": float(mi_mm - null_mean),
                }
            )

    by_animal: dict[str, dict[str, Mapping[str, object]]] = defaultdict(dict)
    for row in mi_rows:
        by_animal[str(row["animal_id"])][str(row["stim_var"])] = row

    delta_rows: list[dict[str, object]] = []
    for aid, stim_map in sorted(by_animal.items()):
        needed = ("dist_fam", "dist_nvl", "dist_locus_a", "dist_locus_b")
        if any(k not in stim_map for k in needed):
            continue
        fam = stim_map["dist_fam"]
        nvl = stim_map["dist_nvl"]
        la = stim_map["dist_locus_a"]
        lb = stim_map["dist_locus_b"]
        d_nov = float(nvl["excess"]) - float(fam["excess"])  # type: ignore[arg-type]
        d_spa = float(lb["excess"]) - float(la["excess"])  # type: ignore[arg-type]

        # nvl-nearest historical locus tag (from bout rows; one novel session/animal)
        tags = [
            str(r.get("nvl_nearest_hist_locus", "") or "")
            for r in rows
            if str(r["animal_id"]) == aid
            and str(r.get("condition_layer", "")) == "novel_obj"
            and str(r.get("nvl_nearest_hist_locus", "") or "") in {"a", "b"}
        ]
        nvl_side = tags[0] if tags else ""
        if nvl_side == "a":
            excess_nvl_side = float(la["excess"])  # type: ignore[arg-type]
            excess_other = float(lb["excess"])  # type: ignore[arg-type]
        elif nvl_side == "b":
            excess_nvl_side = float(lb["excess"])  # type: ignore[arg-type]
            excess_other = float(la["excess"])  # type: ignore[arg-type]
        else:
            excess_nvl_side = float("nan")
            excess_other = float("nan")
        d_nvl_side = excess_nvl_side - excess_other

        delta_rows.append(
            {
                "animal_id": aid,
                "sex": fam["sex"],
                "tx": fam["tx"],
                "cohort": fam["cohort"],
                "phase_layer": fam["phase_layer"],
                "nvl_nearest_hist_locus": nvl_side,
                "excess_fam": fam["excess"],
                "excess_nvl": nvl["excess"],
                "delta_excess_nvl_minus_fam": d_nov,
                "excess_locus_a": la["excess"],
                "excess_locus_b": lb["excess"],
                "delta_excess_locus_b_minus_a": d_spa,
                "excess_nvl_side_hist": excess_nvl_side,
                "excess_other_hist": excess_other,
                "delta_excess_nvl_side_minus_other": d_nvl_side,
                "mi_mm_fam": fam["mi_mm"],
                "mi_mm_nvl": nvl["mi_mm"],
                "mi_mm_locus_a": la["mi_mm"],
                "mi_mm_locus_b": lb["mi_mm"],
                "n_bouts": fam["n_bouts"],
            }
        )

    group_tests = _group_tests_delta(delta_rows)
    # Paired signed-rank on each Δ (is contrast systematically nonzero?)
    for metric, key in (
        ("delta_excess_nvl_minus_fam", "novelty_paired"),
        ("delta_excess_locus_b_minus_a", "spatial_paired"),
        ("delta_excess_nvl_side_minus_other", "nvl_side_paired"),
    ):
        vals = [float(r[metric]) for r in delta_rows if np.isfinite(float(r[metric]))]
        if len(vals) < 2:
            continue
        stat, p = stats.wilcoxon(vals, alternative="two-sided", zero_method="wilcox")
        group_tests.append(
            {
                "sex_stratum": "all",
                "factor": key,
                "level_a": metric,
                "level_b": "0",
                "n_a": len(vals),
                "n_b": 0,
                "median_a": float(np.median(vals)),
                "median_b": 0.0,
                "stat": float(stat),
                "p": float(p),
                "test": "wilcoxon_signed_rank",
                "metric": metric,
            }
        )
    # Spatial / nvl-side: tx tests via metric alias into novelty Δ slot
    for metric, prefix in (
        ("delta_excess_locus_b_minus_a", "spatial"),
        ("delta_excess_nvl_side_minus_other", "nvl_side"),
    ):
        alias_rows = [
            {
                **dict(r),
                "delta_excess_nvl_minus_fam": r[metric],
            }
            for r in delta_rows
            if np.isfinite(float(r[metric]))
        ]
        for t in _group_tests_delta(alias_rows):
            t = dict(t)
            t["metric"] = metric
            t["factor"] = f"{prefix}_{t['factor']}"
            group_tests.append(t)

    return mi_rows, delta_rows, group_tests, dict(bin_edges_payload)
