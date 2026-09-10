"""Kruskal Δp ~ tx by HDBSCAN cluster × phase (mapped id per model × cluster)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi._pub_style import SESSIONS, SEX_ORDER
from nor_object_mi.cluster13_tx_delta import STEPS, kruskal_condition
from nor_object_mi.simpler_first_da import apply_bh_grouped, jaccard

NOISE_CLUSTER = -1


def representative_cluster_ids(
    proto: pd.DataFrame,
    *,
    include_noise: bool = True,
) -> pd.DataFrame:
    """One raw_syllable_id per model × cluster_id (max n_bouts within cluster).

    Noise (``cluster_id == -1``) is included by default as one representative
    syllable per model (same max-``n_bouts`` rule).
    """
    need = {"model", "cluster_id", "raw_syllable_id", "n_bouts"}
    missing = need - set(proto.columns)
    if missing:
        raise ValueError(f"proto missing {sorted(missing)}")
    if include_noise:
        sub = proto.copy()
    else:
        sub = proto[proto["cluster_id"] >= 0].copy()
    if sub.empty:
        return pd.DataFrame(columns=sorted(need))
    idx = sub.groupby(["model", "cluster_id"], sort=True)["n_bouts"].idxmax()
    return sub.loc[idx, ["model", "cluster_id", "raw_syllable_id", "n_bouts"]].reset_index(drop=True)


def order_cluster_ids(cluster_ids: list[int] | pd.Series) -> list[int]:
    """Non-negative ids ascending, then noise (−1) last."""
    ids = sorted({int(x) for x in cluster_ids})
    pos = [c for c in ids if c >= 0]
    neg = [c for c in ids if c < 0]
    return pos + neg


def cluster_axis_label(cluster_id: int) -> str:
    return "noise" if int(cluster_id) < 0 else str(int(cluster_id))


def attach_column_bh(
    tests: pd.DataFrame,
    column_group_cols: list[str],
) -> pd.DataFrame:
    """Second BH family within each heatmap column (across rows).

    Adds ``q_bh_col`` / ``hit_fdr05_col`` without changing panel ``q_bh`` /
    ``hit_fdr05``. Claim: among starred cells *in that column*, expected FDR ≤ 5%.
    """
    return apply_bh_grouped(
        tests,
        column_group_cols,
        q_col="q_bh_col",
        hit_fdr_col="hit_fdr05_col",
        write_hit_p05=False,
    )


def attach_cluster_ids(deltas: pd.DataFrame, rep: pd.DataFrame) -> pd.DataFrame:
    """Keep presence/novelty steps with cluster_id from representative map."""
    keys = rep[["model", "raw_syllable_id", "cluster_id"]].drop_duplicates()
    out = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
    return out[out["step"].isin(STEPS)].copy()


def animal_median_delta_p_by_cluster(mapped: pd.DataFrame) -> pd.DataFrame:
    """One row per cluster × animal × phase × step: median Δp across models."""
    keys = ["cluster_id", "animal_id", "sex", "condition", "session", "step"]
    rows: list[dict[str, object]] = []
    for key_vals, g in mapped.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g["delta_p"], errors="coerce").to_numpy(dtype=float)
        v = v[v == v]
        rows.append(
            {
                **key_map,
                "delta_p": float(np.median(v)) if v.size else float("nan"),
                "n_models": int(g["model"].nunique()),
                "n_finite": int(v.size),
            }
        )
    return pd.DataFrame(rows)


def kruskal_by_cluster_session_step_sex(med: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx inside each cluster × phase × step × sex.

    Panel BH family = cluster × phase within each sex × step.
    Column BH family = clusters within each sex × step × phase (``q_bh_col``).
    """
    rows: list[dict[str, object]] = []
    clusters = order_cluster_ids(med["cluster_id"])
    for cid in clusters:
        sub_c = med[med["cluster_id"] == cid]
        for phase in SESSIONS:
            for step in STEPS:
                for sex in SEX_ORDER:
                    g = sub_c[
                        (sub_c["session"] == phase)
                        & (sub_c["step"] == step)
                        & (sub_c["sex"] == sex)
                    ]
                    rec = kruskal_condition(g)
                    rows.append(
                        {
                            "cluster_id": cid,
                            "session": phase,
                            "step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    out = apply_bh_grouped(pd.DataFrame(rows), ["sex", "step"])
    return attach_column_bh(out, ["sex", "step", "session"])


def cluster_syllable_ids(proto: pd.DataFrame, cluster_id: int = 13) -> pd.DataFrame:
    """All model × raw_syllable_id rows for one HDBSCAN cluster (may be >1 syllable/model)."""
    need = {"model", "cluster_id", "raw_syllable_id", "n_bouts"}
    missing = need - set(proto.columns)
    if missing:
        raise ValueError(f"proto missing {sorted(missing)}")
    sub = proto[proto["cluster_id"] == cluster_id].copy()
    cols = list(need)
    if "ss" in proto.columns:
        cols.append("ss")
    return sub[cols].reset_index(drop=True)


def attach_model_cluster_deltas(deltas: pd.DataFrame, cmap: pd.DataFrame) -> pd.DataFrame:
    """Keep presence/novelty steps for each model's cluster syllable id(s)."""
    keys = cmap[["model", "raw_syllable_id"]].drop_duplicates()
    out = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
    return out[out["step"].isin(STEPS)].copy()


def animal_delta_p_by_model(mapped: pd.DataFrame) -> pd.DataFrame:
    """One row per model × animal × phase × step × tx; median Δp if multiple syllables."""
    keys = ["model", "animal_id", "sex", "condition", "session", "step"]
    rows: list[dict[str, object]] = []
    for key_vals, g in mapped.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g["delta_p"], errors="coerce").to_numpy(dtype=float)
        v = v[np.isfinite(v)]
        rows.append(
            {
                **key_map,
                "delta_p": float(np.median(v)) if v.size else float("nan"),
                "n_syllables": int(g["raw_syllable_id"].nunique()),
                "n_finite": int(v.size),
            }
        )
    return pd.DataFrame(rows)


def kruskal_by_model_session_step_sex(med: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx inside each model × phase × step × sex.

    BH family = model × phase cells within each sex × step panel.
    """
    rows: list[dict[str, object]] = []
    models = sorted(str(x) for x in med["model"].unique())
    for model in models:
        sub_m = med[med["model"] == model]
        for phase in SESSIONS:
            for step in STEPS:
                for sex in SEX_ORDER:
                    g = sub_m[
                        (sub_m["session"] == phase)
                        & (sub_m["step"] == step)
                        & (sub_m["sex"] == sex)
                    ]
                    rec = kruskal_condition(g)
                    rows.append(
                        {
                            "model": model,
                            "session": phase,
                            "step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    out = pd.DataFrame(rows)
    return apply_bh_grouped(out, ["sex", "step"])


def model_row_labels(models: list[str], cmap: pd.DataFrame) -> list[str]:
    """Short y-axis labels: ss when present, else trailing model token."""
    ss_by_model = (
        cmap.drop_duplicates("model").set_index("model")["ss"].astype(int).to_dict()
        if "ss" in cmap.columns
        else {}
    )
    labels: list[str] = []
    for model in models:
        if model in ss_by_model:
            labels.append(f"ss-{ss_by_model[model]}")
        else:
            labels.append(str(model).split("_")[-1][:12])
    return labels


def filter_presence_novelty(deltas: pd.DataFrame) -> pd.DataFrame:
    """Keep presence/novelty condition steps only."""
    return deltas[deltas["step"].isin(STEPS)].copy()


def kruskal_by_syllable_session_step_sex(animals: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx inside each raw_syllable_id × phase × step × sex.

    Caller should pass one kpMS model (ids are model-local). BH family =
    syllable × phase cells within each sex × step panel.
    """
    need = {"raw_syllable_id", "animal_id", "sex", "condition", "session", "step", "delta_p"}
    missing = need - set(animals.columns)
    if missing:
        raise ValueError(f"animals missing {sorted(missing)}")
    rows: list[dict[str, object]] = []
    sylls = sorted(int(x) for x in animals["raw_syllable_id"].unique())
    for sid in sylls:
        sub_s = animals[animals["raw_syllable_id"] == sid]
        for phase in SESSIONS:
            for step in STEPS:
                for sex in SEX_ORDER:
                    g = sub_s[
                        (sub_s["session"] == phase)
                        & (sub_s["step"] == step)
                        & (sub_s["sex"] == sex)
                    ]
                    rec = kruskal_condition(g)
                    rows.append(
                        {
                            "raw_syllable_id": sid,
                            "session": phase,
                            "step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    out = pd.DataFrame(rows)
    return apply_bh_grouped(out, ["sex", "step"])


def kruskal_by_syllable_da_locus_sex(animals: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx per syllable × step × phase × sex; BH within sex (whole panel).

    Locus axis matches co-occurrence columns with sex stripped: ``step|phase``.
    Panel family = all syllable × locus cells for that sex.
    """
    need = {"raw_syllable_id", "animal_id", "sex", "condition", "session", "step", "delta_p"}
    missing = need - set(animals.columns)
    if missing:
        raise ValueError(f"animals missing {sorted(missing)}")
    rows: list[dict[str, object]] = []
    sylls = sorted(int(x) for x in animals["raw_syllable_id"].unique())
    for sid in sylls:
        sub_s = animals[animals["raw_syllable_id"] == sid]
        for step in STEPS:
            for phase in SESSIONS:
                for sex in SEX_ORDER:
                    g = sub_s[
                        (sub_s["session"] == phase)
                        & (sub_s["step"] == step)
                        & (sub_s["sex"] == sex)
                    ]
                    rec = kruskal_condition(g)
                    rows.append(
                        {
                            "raw_syllable_id": sid,
                            "session": phase,
                            "step": step,
                            "sex": sex,
                            "locus": f"{step}|{phase}",
                            **rec,
                        }
                    )
    out = pd.DataFrame(rows)
    return apply_bh_grouped(out, ["sex"])


def da_locus_labels() -> list[str]:
    """Y-axis order matching co-occurrence x (sex stripped): alpha step × SESSIONS."""
    return [f"{step}|{phase}" for step in sorted(STEPS) for phase in SESSIONS]


def hit_locus_matrix(
    kr: pd.DataFrame,
    *,
    row_col: str = "cluster_id",
    hit_col: str = "hit_fdr05",
    panel_cols: tuple[str, ...] = ("sex", "step"),
    locus_col: str = "session",
    locus_order: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Binary hit matrix: one row per ``row_col``, columns = panel|locus labels."""
    if kr.empty or hit_col not in kr.columns:
        return pd.DataFrame()
    loci = list(locus_order) if locus_order is not None else sorted(
        kr[locus_col].astype(str).unique()
    )
    if row_col == "cluster_id":
        row_ids: list = order_cluster_ids(kr[row_col])
    else:
        row_ids = sorted(kr[row_col].unique())
    panel_df = kr.loc[:, list(panel_cols)].drop_duplicates().sort_values(list(panel_cols))
    cols_data: dict[str, list[int]] = {}
    for panel in panel_df.itertuples(index=False):
        panel_map = dict(zip(panel_cols, panel, strict=True))
        panel_lab = "·".join(str(panel_map[c]) for c in panel_cols)
        sub = kr
        for c, v in panel_map.items():
            sub = sub[sub[c] == v]
        for loc in loci:
            lab = f"{panel_lab}|{loc}"
            cell = sub[sub[locus_col].astype(str) == str(loc)]
            hit_map = {
                (int(r) if row_col == "cluster_id" else r): bool(h)
                for r, h in zip(cell[row_col], cell[hit_col], strict=False)
            }
            cols_data[lab] = [int(bool(hit_map.get(rid, False))) for rid in row_ids]
    out = pd.DataFrame(cols_data, index=row_ids)
    out.index.name = row_col
    return out


def pairwise_row_jaccard(hit_mat: pd.DataFrame) -> pd.DataFrame:
    """Jaccard similarity of binary hit patterns across rows.

    Two empty hit sets count as identical (Jaccard = 1), so all-null panels
    still show a coherent identity matrix rather than NaNs.
    """
    if hit_mat.empty:
        return pd.DataFrame()
    ids = list(hit_mat.index)
    n = len(ids)
    mat = np.full((n, n), np.nan, dtype=float)
    sets = [set(hit_mat.columns[hit_mat.loc[i].to_numpy(dtype=bool)]) for i in ids]
    for i in range(n):
        mat[i, i] = 1.0
        for j in range(i + 1, n):
            if not sets[i] and not sets[j]:
                v = 1.0
            else:
                v = jaccard(sets[i], sets[j])
            mat[i, j] = v
            mat[j, i] = v
    return pd.DataFrame(mat, index=ids, columns=ids)


def clusters_with_any_hit(
    kr: pd.DataFrame,
    *,
    hit_cols: tuple[str, ...] = ("hit_fdr05", "hit_fdr05_col"),
) -> list[int]:
    """Cluster ids with at least one True in any listed hit column."""
    if kr.empty or "cluster_id" not in kr.columns:
        return []
    mask = np.zeros(len(kr), dtype=bool)
    for col in hit_cols:
        if col in kr.columns:
            mask |= kr[col].fillna(False).astype(bool).to_numpy()
    ids = [int(x) for x in kr.loc[mask, "cluster_id"].unique()]
    return order_cluster_ids(ids)