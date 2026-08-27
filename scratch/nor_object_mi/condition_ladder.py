"""Condition ladder: no_obj → identical → fam|nvl on hist-tagged sides."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Mapping, Sequence

import numpy as np
from scipy import stats

from maze.kpms.behavior_ethogram.stimulus_mi import assign_bins, occupancy_mi

from .compute_mi import edges_from_json, fit_shared_dist_bin_edges
from .presence_mi import _null_circ, _pooled_occupancy

# stim_var keys used in MI rows
STIM_HIST_A = "dist_hist_a"
STIM_HIST_B = "dist_hist_b"
STIM_FAM = "dist_fam"
STIM_NVL = "dist_nvl"


def _streams(
    rows: Sequence[Mapping[str, object]],
    *,
    animal_id: str,
    condition_layer: str,
    field: str,
    edges: np.ndarray,
    symbol_field: str = "raw_syllable_id",
    order_field: str = "bout_index",
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    by_trial: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if str(row["animal_id"]) != animal_id:
            continue
        if str(row.get("condition_layer", "")) != condition_layer:
            continue
        val = float(row[field])
        if not np.isfinite(val):
            continue
        by_trial[str(row["trial_key"])].append(row)
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for trial, trows in by_trial.items():
        trows = sorted(trows, key=lambda r: int(r[order_field]))
        syll = np.asarray([int(r[symbol_field]) for r in trows], dtype=np.int64)
        stim_vals = np.asarray([float(r[field]) for r in trows], dtype=np.float64)
        out[trial] = (syll, assign_bins(stim_vals, edges))
    return out


def compute_ladder_mi(
    rows: Sequence[Mapping[str, object]],
    *,
    n_bins: int = 5,
    n_perm: int = 100,
    seed: int = 42,
    bin_edges_payload: Mapping[str, object] | None = None,
    symbol_field: str = "raw_syllable_id",
    order_field: str = "bout_index",
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Excess MI for hist A/B under no_obj & identical, and fam/nvl under novel_obj.

    Also emits per-animal ladder rows with fam-side / nvl-side remapping from the
    novel session's ``nvl_nearest_hist_locus`` tag.

    ``symbol_field`` / ``order_field`` select the discrete behavior symbol and
    within-trial order (syllable bouts by default; n-gram rows use
    ``pattern_id`` / ``ngram_index``).
    """
    if bin_edges_payload is None:
        # Fit on any real-object bout distances present in the table
        edges, bin_edges_payload = fit_shared_dist_bin_edges(rows, n_bins=n_bins)
    else:
        edges = edges_from_json(bin_edges_payload)

    animals = sorted({str(r["animal_id"]) for r in rows})
    meta: dict[str, Mapping[str, object]] = {}
    for r in rows:
        meta.setdefault(str(r["animal_id"]), r)

    # animal → nvl-nearest hist locus (from novel_obj rows)
    nvl_side: dict[str, str] = {}
    for r in rows:
        if str(r.get("condition_layer", "")) != "novel_obj":
            continue
        tag = str(r.get("nvl_nearest_hist_locus", "") or "")
        if tag in {"a", "b"}:
            nvl_side[str(r["animal_id"])] = tag

    jobs: list[tuple[str, str, str, str]] = [
        ("no_obj", STIM_HIST_A, "bout_mean_dist_locus_a_m", "hist_a"),
        ("no_obj", STIM_HIST_B, "bout_mean_dist_locus_b_m", "hist_b"),
        ("identical_obj", STIM_HIST_A, "bout_mean_dist_locus_a_m", "hist_a"),
        ("identical_obj", STIM_HIST_B, "bout_mean_dist_locus_b_m", "hist_b"),
        ("novel_obj", STIM_FAM, "bout_mean_dist_fam_m", "fam"),
        ("novel_obj", STIM_NVL, "bout_mean_dist_nvl_m", "nvl"),
    ]

    rng = np.random.default_rng(seed)
    mi_rows: list[dict[str, object]] = []
    for aid in animals:
        m = meta[aid]
        for cond, stim_var, field, channel in jobs:
            streams = _streams(
                rows,
                animal_id=aid,
                condition_layer=cond,
                field=field,
                edges=edges,
                symbol_field=symbol_field,
                order_field=order_field,
            )
            if not streams:
                continue
            mi_raw, mi_mm, h_syll, h_stim, n_bouts = _pooled_occupancy(streams)
            if n_bouts == 0:
                continue
            null_mean, null_p = _null_circ(streams, observed_mm=mi_mm, n_perm=n_perm, rng=rng)
            mi_rows.append(
                {
                    "animal_id": aid,
                    "sex": m["sex"],
                    "tx": m["tx"],
                    "cohort": m["cohort"],
                    "phase_layer": m["phase_layer"],
                    "condition_layer": cond,
                    "stim_var": stim_var,
                    "channel": channel,
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

    by: dict[tuple[str, str, str], Mapping[str, object]] = {}
    for row in mi_rows:
        by[(str(row["animal_id"]), str(row["condition_layer"]), str(row["channel"]))] = row

    ladder_rows: list[dict[str, object]] = []
    for aid in animals:
        side_nvl = nvl_side.get(aid, "")
        if side_nvl not in {"a", "b"}:
            continue
        side_fam = "b" if side_nvl == "a" else "a"
        fam_hist = f"hist_{side_fam}"
        nvl_hist = f"hist_{side_nvl}"

        def _ex(cond: str, channel: str) -> float:
            row = by.get((aid, cond, channel))
            if row is None:
                return float("nan")
            return float(row["excess"])  # type: ignore[arg-type]

        m = meta[aid]
        ladder_rows.append(
            {
                "animal_id": aid,
                "sex": m["sex"],
                "tx": m["tx"],
                "cohort": m["cohort"],
                "phase_layer": m["phase_layer"],
                "nvl_nearest_hist_locus": side_nvl,
                "fam_nearest_hist_locus": side_fam,
                # Panel A (fam ladder)
                "excess_no_obj_fam_side": _ex("no_obj", fam_hist),
                "excess_identical_fam_side": _ex("identical_obj", fam_hist),
                "excess_fam_obj": _ex("novel_obj", "fam"),
                # Panel B (nvl ladder)
                "excess_no_obj_nvl_side": _ex("no_obj", nvl_hist),
                "excess_identical_nvl_side": _ex("identical_obj", nvl_hist),
                "excess_nvl_obj": _ex("novel_obj", "nvl"),
            }
        )

    return mi_rows, ladder_rows, dict(bin_edges_payload)


_TX_ORDER = ("noSD", "GHSD", "RBSD")
_SEX_ORDER = ("F", "M")
_LADDER_STEPS: tuple[tuple[str, str, str, str], ...] = (
    ("fam", "no_obj->identical", "excess_no_obj_fam_side", "excess_identical_fam_side"),
    ("fam", "identical->fam_obj", "excess_identical_fam_side", "excess_fam_obj"),
    ("fam", "no_obj->fam_obj", "excess_no_obj_fam_side", "excess_fam_obj"),
    ("nvl", "no_obj->identical", "excess_no_obj_nvl_side", "excess_identical_nvl_side"),
    ("nvl", "identical->nvl_obj", "excess_identical_nvl_side", "excess_nvl_obj"),
    ("nvl", "no_obj->nvl_obj", "excess_no_obj_nvl_side", "excess_nvl_obj"),
)

# Unified long-form test columns (wilcoxon + kruskal).
LADDER_TEST_FIELDS: tuple[str, ...] = (
    "panel",
    "step",
    "sex",
    "test",
    "stat",
    "p",
    "n",
    "median_delta",
    "frac_delta_gt0",
    "n_noSD",
    "n_GHSD",
    "n_RBSD",
    "median_delta_noSD",
    "median_delta_GHSD",
    "median_delta_RBSD",
)


def _step_deltas(
    ladder_rows: Sequence[Mapping[str, object]],
    *,
    left_k: str,
    right_k: str,
    sex: str | None = None,
) -> np.ndarray:
    """Paired step Δ = right − left; optional sex filter (``None`` = all)."""
    deltas: list[float] = []
    for r in ladder_rows:
        if sex is not None and str(r.get("sex", "")) != sex:
            continue
        a = float(r[left_k])
        b = float(r[right_k])
        if np.isfinite(a) and np.isfinite(b):
            deltas.append(b - a)
    return np.asarray(deltas, dtype=np.float64)


def _wilcoxon_row(panel: str, step: str, sex: str, deltas: np.ndarray) -> dict[str, object]:
    if deltas.size < 2:
        return {
            "panel": panel,
            "step": step,
            "sex": sex,
            "test": "wilcoxon_signed_rank",
            "stat": float("nan"),
            "p": float("nan"),
            "n": int(deltas.size),
            "median_delta": float("nan"),
            "frac_delta_gt0": float("nan"),
            "n_noSD": "",
            "n_GHSD": "",
            "n_RBSD": "",
            "median_delta_noSD": "",
            "median_delta_GHSD": "",
            "median_delta_RBSD": "",
        }
    stat, p = stats.wilcoxon(deltas, alternative="two-sided", zero_method="wilcox")
    return {
        "panel": panel,
        "step": step,
        "sex": sex,
        "test": "wilcoxon_signed_rank",
        "stat": float(stat),
        "p": float(p),
        "n": int(deltas.size),
        "median_delta": float(np.median(deltas)),
        "frac_delta_gt0": float(np.mean(deltas > 0)),
        "n_noSD": "",
        "n_GHSD": "",
        "n_RBSD": "",
        "median_delta_noSD": "",
        "median_delta_GHSD": "",
        "median_delta_RBSD": "",
    }


def ladder_wilcoxon_steps(ladder_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Paired Wilcoxon on ladder steps pooled across sex/tx (figure \"pooled steps\").

    Backward-compatible compact rows (no sex column); prefer
    :func:`ladder_wilcoxon_steps_long` for long tables.
    """
    out: list[dict[str, object]] = []
    for panel, step, left_k, right_k in _LADDER_STEPS:
        deltas = _step_deltas(ladder_rows, left_k=left_k, right_k=right_k)
        if deltas.size < 2:
            continue
        row = _wilcoxon_row(panel, step, "all", deltas)
        out.append(
            {
                "panel": row["panel"],
                "step": row["step"],
                "n": row["n"],
                "median_delta": row["median_delta"],
                "frac_delta_gt0": row["frac_delta_gt0"],
                "stat": row["stat"],
                "p": row["p"],
                "test": row["test"],
            }
        )
    return out


def ladder_wilcoxon_steps_long(
    ladder_rows: Sequence[Mapping[str, object]],
    *,
    include_pooled: bool = True,
    include_within_sex: bool = True,
) -> list[dict[str, object]]:
    """Long-form Wilcoxon on step Δ: pooled (``sex=all``) and/or within-sex.

    Within-sex rows still pool across treatments — they ask whether the ladder
    step Δ differs from zero inside each sex, not whether tx differ.
    """
    out: list[dict[str, object]] = []
    sex_levels: list[str | None] = []
    if include_pooled:
        sex_levels.append(None)
    if include_within_sex:
        sex_levels.extend(list(_SEX_ORDER))
    for panel, step, left_k, right_k in _LADDER_STEPS:
        for sex_f in sex_levels:
            deltas = _step_deltas(ladder_rows, left_k=left_k, right_k=right_k, sex=sex_f)
            sex_label = "all" if sex_f is None else sex_f
            out.append(_wilcoxon_row(panel, step, sex_label, deltas))
    return out


def ladder_within_sex_tx_kruskal_long(
    ladder_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Long-form within-sex Kruskal–Wallis on ladder step Δ across treatments."""
    out: list[dict[str, object]] = []
    for panel, step, left_k, right_k in _LADDER_STEPS:
        for sex in _SEX_ORDER:
            by_tx: dict[str, list[float]] = defaultdict(list)
            for r in ladder_rows:
                if str(r.get("sex", "")) != sex:
                    continue
                tx = str(r.get("tx", ""))
                if tx not in _TX_ORDER:
                    continue
                a = float(r[left_k])
                b = float(r[right_k])
                if np.isfinite(a) and np.isfinite(b):
                    by_tx[tx].append(b - a)
            n_by_tx = {t: len(by_tx[t]) for t in _TX_ORDER}
            med_by_tx = {
                t: (float(np.median(by_tx[t])) if by_tx[t] else float("nan")) for t in _TX_ORDER
            }
            samples = [by_tx[t] for t in _TX_ORDER]
            if any(len(s) < 2 for s in samples):
                stat = float("nan")
                p = float("nan")
            else:
                stat_v, p_v = stats.kruskal(*samples)
                stat, p = float(stat_v), float(p_v)
            all_d = np.concatenate([np.asarray(by_tx[t], dtype=np.float64) for t in _TX_ORDER if by_tx[t]])
            out.append(
                {
                    "panel": panel,
                    "step": step,
                    "sex": sex,
                    "test": "kruskal",
                    "stat": stat,
                    "p": p,
                    "n": int(all_d.size),
                    "median_delta": float(np.median(all_d)) if all_d.size else float("nan"),
                    "frac_delta_gt0": float(np.mean(all_d > 0)) if all_d.size else float("nan"),
                    "n_noSD": n_by_tx["noSD"],
                    "n_GHSD": n_by_tx["GHSD"],
                    "n_RBSD": n_by_tx["RBSD"],
                    "median_delta_noSD": med_by_tx["noSD"],
                    "median_delta_GHSD": med_by_tx["GHSD"],
                    "median_delta_RBSD": med_by_tx["RBSD"],
                }
            )
    return out


def ladder_tests_long(ladder_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Wilcoxon (pooled + within-sex) and within-sex tx Kruskal in one long table."""
    return ladder_wilcoxon_steps_long(ladder_rows) + ladder_within_sex_tx_kruskal_long(ladder_rows)


def summarize_side_tags(ladder_rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    counts = Counter(str(r.get("nvl_nearest_hist_locus", "")) for r in ladder_rows)
    return {"nvl_nearest_hist_locus_counts": dict(counts), "n_animals": len(ladder_rows)}
