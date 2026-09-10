"""Second-order paired Δp_k: compose two within-animal pairings.

(b) ``session_on_trial``: condition-step Δ at each NOR phase, then phase-step
    on that Δ — moderation of presence/novelty/span reallocation across protocol.

(c) ``trial_on_session``: phase-step Δ at each condition, then condition-step
    on that Δ — moderation of BL→TX (etc.) shifts across arena layouts.

Stage B (optional downstream): Kruskal Δ²p ~ tx within sex (independent tx arms).
"""

from __future__ import annotations

import pandas as pd

from nor_object_mi.simpler_first_da import DA_STEPS
from nor_object_mi.simpler_first_session_paired import PHASE_STEPS, PHASE_STEP_NAMES
from nor_object_mi.simpler_first_presence import STEPS

PAIR_KEYS = ("model", "animal_id", "raw_syllable_id", "sex", "condition")


def _pair_outer(
    sub: pd.DataFrame,
    *,
    outer_step: str,
    outer_left: str,
    outer_right: str,
    pair_col: str,
    axis: str,
) -> pd.DataFrame:
    """Difference of first-order Δp across ``pair_col`` (right − left)."""
    if sub.empty:
        return pd.DataFrame()
    left = sub[sub[pair_col].astype(str) == outer_left]
    right = sub[sub[pair_col].astype(str) == outer_right]
    if left.empty or right.empty:
        return pd.DataFrame()
    m = left.merge(
        right,
        on=list(PAIR_KEYS),
        how="inner",
        suffixes=("_left", "_right"),
    )
    if m.empty:
        return pd.DataFrame()
    dl = pd.to_numeric(m["delta_p_left"], errors="coerce")
    dr = pd.to_numeric(m["delta_p_right"], errors="coerce")
    out = m[list(PAIR_KEYS)].copy()
    out["delta_p_left"] = dl
    out["delta_p_right"] = dr
    out["delta_p"] = dr - dl
    out["outer_left"] = outer_left
    out["outer_right"] = outer_right
    out["axis"] = axis
    if axis == "session_on_trial":
        out["session_step"] = outer_step
    else:
        out["condition_step"] = outer_step
    return out


def compose_nested_deltas(
    first: pd.DataFrame,
    *,
    axis: str,
) -> pd.DataFrame:
    """Build all second-order Δp rows for one axis."""
    if first.empty:
        return pd.DataFrame()
    first = first.copy()
    parts: list[pd.DataFrame] = []

    if axis == "session_on_trial":
        if "condition_step" not in first.columns:
            first["condition_step"] = first["step"].astype(str)
        if "session" not in first.columns:
            raise ValueError("session_on_trial requires session on first-order deltas")
        for cond_step in DA_STEPS:
            sub = first[first["condition_step"].astype(str) == cond_step]
            for outer_step, outer_left, outer_right in PHASE_STEPS:
                part = _pair_outer(
                    sub,
                    outer_step=outer_step,
                    outer_left=outer_left,
                    outer_right=outer_right,
                    pair_col="session",
                    axis=axis,
                )
                if part.empty:
                    continue
                part["condition_step"] = cond_step
                parts.append(part)
    elif axis == "trial_on_session":
        if "session_step" not in first.columns:
            if "step" in first.columns:
                first["session_step"] = first["step"].astype(str)
            else:
                raise ValueError("trial_on_session requires session_step on first-order deltas")
        if "trial" not in first.columns:
            raise ValueError("trial_on_session requires trial on first-order deltas")
        for session_step in PHASE_STEP_NAMES:
            sub = first[first["session_step"].astype(str) == session_step]
            for outer_step, outer_left, outer_right in STEPS:
                part = _pair_outer(
                    sub,
                    outer_step=outer_step,
                    outer_left=outer_left,
                    outer_right=outer_right,
                    pair_col="trial",
                    axis=axis,
                )
                if part.empty:
                    continue
                part["session_step"] = session_step
                parts.append(part)
    else:
        raise ValueError(f"axis must be session_on_trial or trial_on_session, got {axis!r}")

    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def load_condition_step_first_order(da_dir) -> pd.DataFrame:
    """1st-order condition-step Δp at each NOR phase (``simpler_first_da``)."""
    path = da_dir / "da_syllable_deltas_per_animal.csv"
    return pd.read_csv(path).assign(condition_step=lambda d: d["step"].astype(str))


def load_session_step_first_order(pp_dir) -> pd.DataFrame:
    """1st-order phase-step Δp at each condition (``simpler_first_session_paired``)."""
    path = pp_dir / "session_paired_da_deltas_per_animal.csv"
    df = pd.read_csv(path)
    if "session_step" not in df.columns:
        df = df.assign(session_step=df["step"].astype(str))
    return df


def paired_n_by_outer_step(
    df: pd.DataFrame,
    *,
    axis: str,
    animal_col: str = "animal_id",
) -> dict[str, int]:
    """Unique animals per outer-step column (session_step for b, condition_step for c)."""
    if df.empty:
        return {}
    if axis == "session_on_trial":
        step_col = "session_step"
        steps = PHASE_STEP_NAMES
    elif axis == "trial_on_session":
        step_col = "condition_step"
        steps = DA_STEPS
    else:
        raise ValueError(axis)
    out: dict[str, int] = {}
    for step in steps:
        sub = df[df[step_col].astype(str) == step]
        if sub.empty:
            continue
        out[step] = int(sub[animal_col].nunique())
    return out


def paired_n_by_inner_step(
    df: pd.DataFrame,
    *,
    axis: str,
    animal_col: str = "animal_id",
) -> dict[str, int]:
    """Unique animals per inner-step panel (condition_step for b, session_step for c)."""
    if df.empty:
        return {}
    if axis == "session_on_trial":
        step_col = "condition_step"
        steps = DA_STEPS
    elif axis == "trial_on_session":
        step_col = "session_step"
        steps = PHASE_STEP_NAMES
    else:
        raise ValueError(axis)
    out: dict[str, int] = {}
    for step in steps:
        sub = df[df[step_col].astype(str) == step]
        if sub.empty:
            continue
        out[step] = int(sub[animal_col].nunique())
    return out


def paired_n_grid(
    df: pd.DataFrame,
    *,
    axis: str,
    animal_col: str = "animal_id",
) -> dict[tuple[str, str], int]:
    """Paired n for each panel × outer-column cell."""
    if df.empty:
        return {}
    if axis == "session_on_trial":
        row_key, col_key = "condition_step", "session_step"
    elif axis == "trial_on_session":
        row_key, col_key = "session_step", "condition_step"
    else:
        raise ValueError(axis)
    out: dict[tuple[str, str], int] = {}
    for (rk, ck), g in df.groupby([row_key, col_key], sort=True):
        out[(str(rk), str(ck))] = int(g[animal_col].nunique())
    return out


def cond_step_axis_label(step: str, n: int | None) -> str:
    lab = COND_STEP_LAB.get(step, step)
    if n is None:
        return lab
    return f"{lab}\nn={n}"


def cond_step_axis_labels(session_step: str, n_grid: dict[tuple[str, str], int]) -> list[str]:
    return [cond_step_axis_label(s, n_grid.get((session_step, s))) for s in DA_STEPS]


COND_STEP_LAB = {
    "no_obj->id_obj": "presence",
    "id_obj->nvl_obj": "novelty",
    "no_obj->nvl_obj": "span",
}

__all__ = [
    "COND_STEP_LAB",
    "compose_nested_deltas",
    "cond_step_axis_label",
    "cond_step_axis_labels",
    "load_condition_step_first_order",
    "load_session_step_first_order",
    "paired_n_by_inner_step",
    "paired_n_by_outer_step",
    "paired_n_grid",
]
