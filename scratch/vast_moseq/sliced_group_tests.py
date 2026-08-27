"""One- and two-hold Mann–Whitney slices on animal-level Δp (VAST cohort factors)."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterator, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from nor_object_mi.simpler_first_da import apply_bh_grouped
from vast_moseq.cohort_meta import SLICE_FACTORS, SEX_ORDER, STRAIN_ORDER, TX_ORDER

FACTOR_LEVELS: dict[str, tuple[str, ...]] = {
    "sex": SEX_ORDER,
    "strain": STRAIN_ORDER,
    "tx": TX_ORDER,
}


@dataclass(frozen=True)
class SliceSpec:
    hold: tuple[tuple[str, str], ...]
    contrast_factor: str
    level_a: str
    level_b: str


def _hold_columns(hold: Mapping[str, str]) -> dict[str, str]:
    return {
        "hold_sex": hold.get("sex", ""),
        "hold_strain": hold.get("strain", ""),
        "hold_tx": hold.get("tx", ""),
    }


def _levels_present(df: pd.DataFrame) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for factor in SLICE_FACTORS:
        if factor not in df.columns:
            out[factor] = []
            continue
        vals = sorted(str(x) for x in df[factor].dropna().unique() if str(x))
        out[factor] = [v for v in FACTOR_LEVELS[factor] if v in vals]
    return out


def _iter_slice_specs(levels: Mapping[str, Sequence[str]]) -> Iterator[SliceSpec]:
    for hold_factor in SLICE_FACTORS:
        for hold_level in levels.get(hold_factor, ()):
            for contrast_factor in (f for f in SLICE_FACTORS if f != hold_factor):
                contrast_levels = list(levels.get(contrast_factor, ()))
                for i, level_a in enumerate(contrast_levels):
                    for level_b in contrast_levels[i + 1 :]:
                        yield SliceSpec(
                            hold=((hold_factor, hold_level),),
                            contrast_factor=contrast_factor,
                            level_a=level_a,
                            level_b=level_b,
                        )
    for hold_a, hold_b in combinations(SLICE_FACTORS, 2):
        contrast_factor = next(f for f in SLICE_FACTORS if f not in (hold_a, hold_b))
        for hold_a_level in levels.get(hold_a, ()):
            for hold_b_level in levels.get(hold_b, ()):
                contrast_levels = list(levels.get(contrast_factor, ()))
                for i, level_a in enumerate(contrast_levels):
                    for level_b in contrast_levels[i + 1 :]:
                        yield SliceSpec(
                            hold=((hold_a, hold_a_level), (hold_b, hold_b_level)),
                            contrast_factor=contrast_factor,
                            level_a=level_a,
                            level_b=level_b,
                        )


def _matches_hold(row: Mapping[str, object], hold: Mapping[str, str]) -> bool:
    for factor, level in hold.items():
        if str(row[factor]) != level:
            return False
    return True


def _mann_whitney_row(
    subset: pd.DataFrame,
    spec: SliceSpec,
    *,
    phase_layer: str,
    step: str,
    value_col: str = "delta_p",
) -> dict[str, object] | None:
    hold_map = dict(spec.hold)
    rows = [r for _, r in subset.iterrows() if _matches_hold(r, hold_map)]
    if not rows:
        return None
    g = pd.DataFrame(rows)
    va = pd.to_numeric(g.loc[g[spec.contrast_factor] == spec.level_a, value_col], errors="coerce")
    vb = pd.to_numeric(g.loc[g[spec.contrast_factor] == spec.level_b, value_col], errors="coerce")
    va = va.to_numpy(dtype=np.float64)
    vb = vb.to_numpy(dtype=np.float64)
    va = va[np.isfinite(va)]
    vb = vb[np.isfinite(vb)]
    if va.size < 2 or vb.size < 2:
        stat_f, p_f = float("nan"), float("nan")
    else:
        stat, p = stats.mannwhitneyu(va, vb, alternative="two-sided")
        stat_f, p_f = float(stat), float(p)
    return {
        "phase_layer": phase_layer,
        "step": step,
        **_hold_columns(hold_map),
        "contrast_factor": spec.contrast_factor,
        "level_a": spec.level_a,
        "level_b": spec.level_b,
        "test": "mannwhitneyu",
        "stat": stat_f,
        "p": p_f,
        "n_a": int(va.size),
        "n_b": int(vb.size),
        "median_a": float(np.median(va)) if va.size else float("nan"),
        "median_b": float(np.median(vb)) if vb.size else float("nan"),
    }


def sliced_mann_whitney_tests(med: pd.DataFrame) -> pd.DataFrame:
    """Sliced Δp tests for each phase × step; BH within step × contrast_factor × hold tuple."""
    need = {"animal_id", "sex", "strain", "tx", "phase_layer", "step", "delta_p"}
    missing = need - set(med.columns)
    if missing:
        raise ValueError(f"sliced tests missing columns: {sorted(missing)}")
    levels = _levels_present(med)
    rows: list[dict[str, object]] = []
    for phase in sorted(med["phase_layer"].unique()):
        for step in sorted(med["step"].unique()):
            sub = med[(med["phase_layer"] == phase) & (med["step"] == step)]
            if sub.empty:
                continue
            for spec in _iter_slice_specs(levels):
                rec = _mann_whitney_row(sub, spec, phase_layer=str(phase), step=str(step))
                if rec is not None:
                    rows.append(rec)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["fdr_family"] = "pause_cluster_sliced"
    group_cols = ["step", "contrast_factor", "hold_sex", "hold_strain", "hold_tx"]
    return apply_bh_grouped(out, group_cols)
