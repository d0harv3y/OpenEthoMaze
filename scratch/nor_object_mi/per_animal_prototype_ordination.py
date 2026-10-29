"""2D PCA ordination of per-animal syllable prototypes (flat vs stage-1).

Gold layout (matches ``fig_simpler_first_syllable_signatures`` slides):
PC1 × PC2 scatter (turbo by ``cluster_id``) + feature loadings. All
``num_states`` pooled in one HDBSCAN / one PCA (not split by K).

Regen (OpenEthoMaze repo root):

  uv run python scratch/nor_object_mi/per_animal_prototype_ordination.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h5py
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from maze.kpms.behavior_ethogram.cluster import zscore_features  # noqa: E402
from nor_object_mi._pub_style import (  # noqa: E402
    CONDITION_COLOR,
    CONDITION_ORDER,
    FIGSIZE_DOUBLE,
    INK,
    SEX_MARKER,
    SEX_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_svg,
    type_scale,
)
from nor_object_mi.join_keys import filter_cohort  # noqa: E402
from nor_object_mi.simpler_first_syllable_signatures import (  # noqa: E402
    CLUSTER_POOL_COLS,
    accumulate_chunk_sums,
    prototypes_from_accumulators,
)

DEFAULT_KIN = Path(
    r"D:\sack\datas\impress\nor_per_animal_paramscan"
    r"\_nor_object_mi\simpler_first_syllable_kinematics\syllable_bout_kinematics.csv"
)
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\nor_per_animal_paramscan"
    r"\_nor_object_mi\simpler_first_prototype_ordination"
)
DEFAULT_NOR = Path(r"D:\sack\datas\impress\my_NOR_results.h5")

# Tighter than pooled-ensemble gold (5/3): per-animal clouds need smaller min sizes.
DEFAULT_MIN_CLUSTER_SIZE = 3
DEFAULT_MIN_SAMPLES = 1
DEFAULT_STAGE1_MIN_CLUSTER_SIZE = 2
DEFAULT_STAGE1_MIN_SAMPLES = 1

NOISE_COLOR = "#c8c8c8"
FEATURE_SHORT = {
    "syllable_sig_mean_speed_mps": "speed",
    "syllable_sig_mean_abs_dheading": "|dheading|",
    "syllable_sig_mean_nose_tail_m": "nose-tail",
    "syllable_mean_iqr_speed_mps": "IQR speed",
    "syllable_mean_iqr_abs_dheading": "IQR |dh|",
    "syllable_mean_iqr_nose_tail_m": "IQR size",
    "syllable_mean_duration_s": "duration",
    "syllable_mean_net_dheading_rad": "net dh",
    "syllable_mean_straightness": "straight",
}
SIG_RENAME = {
    "bout_mean_speed_mps": "syllable_sig_mean_speed_mps",
    "bout_mean_abs_dheading": "syllable_sig_mean_abs_dheading",
    "bout_mean_nose_tail_m": "syllable_sig_mean_nose_tail_m",
    "bout_iqr_speed_mps": "syllable_mean_iqr_speed_mps",
    "bout_iqr_abs_dheading": "syllable_mean_iqr_abs_dheading",
    "bout_iqr_nose_tail_m": "syllable_mean_iqr_nose_tail_m",
    "bout_duration_s": "syllable_mean_duration_s",
    "bout_net_dheading_rad": "syllable_mean_net_dheading_rad",
    "bout_straightness": "syllable_mean_straightness",
}
CLUSTER_FEAT_COLS = tuple(SIG_RENAME.values())


def _animal_from_model(model: str) -> str:
    return str(model).split("_paramscan_", 1)[0]


def animal_sex_condition(nor_h5_path: Path) -> pd.DataFrame:
    """One row per kept animal: sex, condition (tx), cohort."""
    rows: list[dict[str, str]] = []
    with h5py.File(nor_h5_path, "r") as nor_h5:
        kept = set(filter_cohort(nor_h5)["kept_ids"])  # type: ignore[arg-type]
        for aid in sorted(kept):
            node = nor_h5[aid]
            cond = str(node.attrs.get("condition", "") or node.attrs.get("tx", "") or "")
            sex = str(node.attrs.get("sex", "") or "")
            cohort = str(node.attrs.get("cohort", "") or "")
            rows.append(
                {
                    "animal_id": str(aid),
                    "sex": sex,
                    "condition": cond,
                    "cohort": cohort,
                }
            )
    return pd.DataFrame(rows)


def attach_animal_labels(df: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["animal_id"] = out["animal_id"].astype(str)
    lab = labels.copy()
    lab["animal_id"] = lab["animal_id"].astype(str)
    return out.merge(lab, on="animal_id", how="left")


def pool_flat_prototypes(kin_csv: Path, *, chunksize: int) -> pd.DataFrame:
    read_cols = ["model", "ss", "raw_syllable_id", *CLUSTER_POOL_COLS]
    sums: dict[tuple, np.ndarray] = {}
    counts: dict[tuple, np.ndarray] = {}
    n_bouts: dict[tuple, int] = {}
    n_rows = 0
    print(f"Pooling flat prototypes from {kin_csv}", flush=True)
    for chunk in pd.read_csv(kin_csv, usecols=read_cols, chunksize=chunksize):
        accumulate_chunk_sums(chunk, sums, counts, n_bouts, CLUSTER_POOL_COLS)
        n_rows += len(chunk)
        if n_rows % (chunksize * 2) == 0 or n_rows == chunksize:
            print(f"  rows={n_rows:,} keys={len(sums):,}", flush=True)
    proto = prototypes_from_accumulators(sums, counts, n_bouts, CLUSTER_POOL_COLS)
    proto["animal_id"] = proto["model"].map(_animal_from_model)
    proto["ss"] = proto["ss"].astype(int)
    print(f"  flat prototypes={len(proto):,} from {n_rows:,} bout rows", flush=True)
    return proto


def _finite_feature_mask(df: pd.DataFrame) -> np.ndarray:
    mat = df[list(CLUSTER_FEAT_COLS)].to_numpy(dtype=np.float64)
    return np.isfinite(mat).all(axis=1)


def pca_ordination(z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """PCA on row-wise z-scored matrix. Returns scores, loadings (p×k), var frac."""
    x = np.asarray(z, dtype=np.float64)
    x = x - np.nanmean(x, axis=0, keepdims=True)
    x = np.nan_to_num(x, nan=0.0)
    _u, s, vt = np.linalg.svd(x, full_matrices=False)
    scores = x @ vt.T
    loadings = vt.T
    var = (s**2) / max(float(np.sum(s**2)), 1e-12)
    return scores, loadings, var


def run_hdbscan(
    proto: pd.DataFrame,
    *,
    min_cluster_size: int,
    min_samples: int,
) -> tuple[pd.DataFrame, np.ndarray, dict]:
    import hdbscan

    keep = _finite_feature_mask(proto)
    fit = proto.loc[keep].copy().reset_index(drop=True)
    mat = fit[list(CLUSTER_FEAT_COLS)].to_numpy(dtype=np.float64)
    z, mean, std = zscore_features(mat)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=int(min_cluster_size),
        min_samples=int(min_samples),
        metric="euclidean",
    )
    labels = np.asarray(clusterer.fit_predict(z), dtype=np.int64)
    fit["cluster_id"] = labels
    scores, loadings, var = pca_ordination(z)
    fit["pc1"] = scores[:, 0]
    fit["pc2"] = scores[:, 1]
    summary = {
        "n_fit": int(len(fit)),
        "n_dropped_nonfinite": int((~keep).sum()),
        "n_clusters": int(len({int(x) for x in labels.tolist() if int(x) >= 0})),
        "n_noise": int(np.sum(labels < 0)),
        "noise_frac": float(np.mean(labels < 0)) if len(labels) else float("nan"),
        "min_cluster_size": int(min_cluster_size),
        "min_samples": int(min_samples),
        "pca_var_ratio": var[:3].tolist(),
        "zscore_mean": mean.tolist(),
        "zscore_std": std.tolist(),
    }
    return fit, loadings, summary


def stage1_within_animal_prototypes(
    flat: pd.DataFrame,
    *,
    min_cluster_size: int,
    min_samples: int,
    min_bouts: int,
) -> tuple[pd.DataFrame, dict]:
    """Equate syllables within each animal across all models / K; return centroids."""
    import hdbscan

    rows_list: list[dict] = []
    n_animals = 0
    n_within_clusters = 0
    n_singletons = 0
    for animal_id, sub0 in flat.groupby("animal_id", sort=True):
        sub = sub0[sub0["n_bouts"] >= min_bouts].copy()
        sub = sub.loc[_finite_feature_mask(sub)].reset_index(drop=True)
        if sub.empty:
            continue
        n_animals += 1
        mat = sub[list(CLUSTER_FEAT_COLS)].to_numpy(dtype=np.float64)
        z, _, _ = zscore_features(mat)
        if len(sub) < max(min_cluster_size, 3):
            for _, r in sub.iterrows():
                rec = {c: float(r[c]) for c in CLUSTER_FEAT_COLS}
                rec.update(
                    {
                        "animal_id": str(animal_id),
                        "stage1_cluster_id": -1,
                        "n_member_prototypes": 1,
                        "n_bouts": int(r["n_bouts"]),
                        "member_models": str(r["model"]),
                        "member_ss": str(int(r["ss"])),
                    }
                )
                rows_list.append(rec)
                n_singletons += 1
            continue
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=int(min_cluster_size),
            min_samples=int(min_samples),
            metric="euclidean",
        )
        labels = np.asarray(clusterer.fit_predict(z), dtype=np.int64)
        sub = sub.copy()
        sub["_s1"] = labels
        for cid, grp in sub.groupby("_s1", sort=True):
            cid_i = int(cid)
            if cid_i < 0:
                for _, r in grp.iterrows():
                    rec = {c: float(r[c]) for c in CLUSTER_FEAT_COLS}
                    rec.update(
                        {
                            "animal_id": str(animal_id),
                            "stage1_cluster_id": -1,
                            "n_member_prototypes": 1,
                            "n_bouts": int(r["n_bouts"]),
                            "member_models": str(r["model"]),
                            "member_ss": str(int(r["ss"])),
                        }
                    )
                    rows_list.append(rec)
                    n_singletons += 1
                continue
            w = grp["n_bouts"].to_numpy(dtype=np.float64)
            w = np.where(np.isfinite(w) & (w > 0), w, 1.0)
            feats = grp[list(CLUSTER_FEAT_COLS)].to_numpy(dtype=np.float64)
            centroid = np.average(feats, axis=0, weights=w)
            rec = {c: float(centroid[j]) for j, c in enumerate(CLUSTER_FEAT_COLS)}
            rec.update(
                {
                    "animal_id": str(animal_id),
                    "stage1_cluster_id": cid_i,
                    "n_member_prototypes": int(len(grp)),
                    "n_bouts": int(grp["n_bouts"].sum()),
                    "member_models": ";".join(sorted(set(grp["model"].astype(str)))),
                    "member_ss": ";".join(
                        str(int(x)) for x in sorted(set(grp["ss"].astype(int)))
                    ),
                }
            )
            rows_list.append(rec)
            n_within_clusters += 1

    out = pd.DataFrame(rows_list)
    summary = {
        "n_animals": n_animals,
        "n_stage1_prototypes": int(len(out)),
        "n_within_animal_clusters": n_within_clusters,
        "n_singletons_or_noise": n_singletons,
        "min_cluster_size": int(min_cluster_size),
        "min_samples": int(min_samples),
    }
    return out, summary


def build_cluster_color_lookup(
    cluster_id_series: pd.Series,
) -> tuple[dict[int, tuple[float, float, float, float]], list[int], ListedColormap]:
    cluster_ids = sorted(int(x) for x in cluster_id_series.unique() if int(x) >= 0)
    n = len(cluster_ids)
    base = plt.get_cmap("turbo")
    lookup: dict[int, tuple[float, float, float, float]] = {
        cid: base(i / max(n - 1, 1)) for i, cid in enumerate(cluster_ids)
    }
    lookup[-1] = mcolors.to_rgba(NOISE_COLOR)
    listed = ListedColormap([lookup[cid] for cid in cluster_ids]) if cluster_ids else ListedColormap([NOISE_COLOR])
    return lookup, cluster_ids, listed


def colors_for_cluster_ids(
    cluster_ids: pd.Series | np.ndarray,
    lookup: dict[int, tuple[float, float, float, float]],
) -> np.ndarray:
    ids = np.asarray(cluster_ids, dtype=np.int64)
    return np.vstack([lookup.get(int(c), lookup[-1]) for c in ids])


def add_cluster_id_colorbar(
    fig: plt.Figure,
    ax: plt.Axes,
    cluster_ids: list[int],
    listed: ListedColormap,
    *,
    dest: str,
) -> None:
    if not cluster_ids:
        return
    ts = type_scale(dest)
    n = len(cluster_ids)
    norm = BoundaryNorm(np.arange(n + 1) - 0.5, n)
    sm = ScalarMappable(cmap=listed, norm=norm)
    sm.set_array(np.arange(n))
    cbar = fig.colorbar(sm, ax=ax, fraction=0.05, pad=0.02)
    cbar.set_label("cluster_id", fontsize=ts["legend"])
    tick_at = np.unique(np.round(np.linspace(0, n - 1, min(9, n))).astype(int))
    cbar.set_ticks(tick_at)
    cbar.set_ticklabels([str(cluster_ids[i]) for i in tick_at])


def fig_gold_ordination(
    cl: pd.DataFrame,
    loadings: np.ndarray,
    feat_names: tuple[str, ...],
    var: list[float] | np.ndarray,
    *,
    out_stem: Path,
    dest: str,
    mode_label: str,
    footnote_extra: str,
    hdbscan_note: str,
) -> None:
    """Left: PC1×PC2 turbo fill by cluster_id; sex marker; condition edge.
    Right: feature loadings.
    """
    apply_style(dest=dest)
    ts = type_scale(dest)
    lookup, cluster_ids, listed = build_cluster_color_lookup(cl["cluster_id"])
    noise = cl["cluster_id"] < 0
    s_pt = float(ts["scatter"] if dest == "slides" else ts["violin_scatter"] * 0.35)
    # Slightly larger so condition outlines read on slides.
    s_mark = s_pt * 1.35
    edge_lw = 0.9 if dest == "slides" else 0.55
    pc1_pct = 100.0 * float(var[0])
    pc2_pct = 100.0 * float(var[1])

    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)

    ax = axes[0]
    ax.scatter(
        cl.loc[noise, "pc1"],
        cl.loc[noise, "pc2"],
        s=s_mark * 0.4,
        c=NOISE_COLOR,
        marker="o",
        alpha=0.3,
        edgecolors="none",
        zorder=1,
    )
    clustered = cl.loc[~noise].copy()
    if not clustered.empty:
        for sex in SEX_ORDER:
            for cond in CONDITION_ORDER:
                sub = clustered[
                    (clustered["sex"].astype(str) == sex)
                    & (clustered["condition"].astype(str) == cond)
                ]
                if sub.empty:
                    continue
                ax.scatter(
                    sub["pc1"],
                    sub["pc2"],
                    s=s_mark,
                    marker=SEX_MARKER[sex],
                    c=colors_for_cluster_ids(sub["cluster_id"], lookup),
                    alpha=0.88,
                    edgecolors=CONDITION_COLOR[cond],
                    linewidths=edge_lw,
                    zorder=2,
                )
        # Any rows missing sex/condition still plotted (ink edge).
        known = clustered["sex"].isin(SEX_ORDER) & clustered["condition"].isin(
            CONDITION_ORDER
        )
        other = clustered.loc[~known]
        if not other.empty:
            ax.scatter(
                other["pc1"],
                other["pc2"],
                s=s_mark,
                marker="o",
                c=colors_for_cluster_ids(other["cluster_id"], lookup),
                alpha=0.7,
                edgecolors=INK,
                linewidths=0.3,
                zorder=2,
            )
    ax.set_xlabel(f"PC1 ({pc1_pct:.1f}% var)")
    ax.set_ylabel(f"PC2 ({pc2_pct:.1f}% var)")
    ax.set_title(
        "A  Prototype scores (PC1 × PC2)",
        loc="left",
        fontweight="bold",
        color=INK,
        fontsize=ts["annotation"],
    )
    add_cluster_id_colorbar(fig, ax, cluster_ids, listed, dest=dest)

    sex_handles = [
        Line2D(
            [0],
            [0],
            marker=SEX_MARKER[s],
            color="none",
            markerfacecolor=INK,
            markeredgecolor=INK,
            markersize=8,
            linestyle="None",
            label={"F": "female (○)", "M": "male (▽)"}[s],
        )
        for s in SEX_ORDER
    ]
    cond_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor="white",
            markeredgecolor=CONDITION_COLOR[t],
            markeredgewidth=1.6,
            markersize=8,
            linestyle="None",
            label=t,
        )
        for t in CONDITION_ORDER
    ]
    ax.legend(
        handles=sex_handles + cond_handles,
        loc="best",
        frameon=False,
        fontsize=ts["legend"],
        title="shape = sex · outline = condition",
        title_fontsize=ts["legend"],
    )

    ax = axes[1]
    scale = 0.85 / max(float(np.max(np.abs(loadings[:, :2]))), 1e-12)
    for i, name in enumerate(feat_names):
        lx, ly = loadings[i, 0] * scale, loadings[i, 1] * scale
        ax.arrow(
            0.0,
            0.0,
            lx,
            ly,
            head_width=0.03,
            head_length=0.02,
            fc=INK,
            ec=INK,
            linewidth=0.8,
            zorder=2,
        )
        ax.text(
            lx * 1.08,
            ly * 1.08,
            FEATURE_SHORT.get(name, name),
            fontsize=ts["cell"],
            ha="center",
            va="center",
            color=INK,
        )
    ax.axhline(0, color="#dddddd", linewidth=0.6, zorder=0)
    ax.axvline(0, color="#dddddd", linewidth=0.6, zorder=0)
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(f"PC1 loading ({pc1_pct:.1f}% var)")
    ax.set_ylabel(f"PC2 loading ({pc2_pct:.1f}% var)")
    ax.set_title(
        "B  feature loadings (same z-scored 9-D space as HDBSCAN)",
        loc="left",
        fontweight="bold",
        color=INK,
        fontsize=ts["annotation"],
    )

    n_fit = int(len(cl))
    n_cl = len(cluster_ids)
    n_noise = int(noise.sum())
    fig.suptitle(
        "Syllable IDs do not equate across models, but we can cluster them\n"
        f"by their bouts' kinematic features  ·  {mode_label}",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(
        fig,
        (
            f"PCA on 9 z-scored kinematics ({n_fit} prototypes, n_bouts ≥ 10; all num_states pooled). "
            f"{hdbscan_note} → {n_cl} clusters, {n_noise} noise ({n_noise / max(n_fit, 1):.0%}). "
            f"{footnote_extra} Fill = cluster_id (turbo); shape = sex; outline = condition "
            "(noSD/GHSD/RBSD violin colors). Grey = noise (−1). D only."
        ),
        fontsize=ts["footnote"],
    )
    save_pdf_svg(fig, out_stem)
    plt.close(fig)
    print(f"wrote {out_stem.name}", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kinematics-csv", type=Path, default=DEFAULT_KIN)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--chunksize", type=int, default=250_000)
    ap.add_argument("--min-bouts", type=int, default=10)
    ap.add_argument("--min-cluster-size", type=int, default=DEFAULT_MIN_CLUSTER_SIZE)
    ap.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    ap.add_argument(
        "--stage1-min-cluster-size",
        type=int,
        default=DEFAULT_STAGE1_MIN_CLUSTER_SIZE,
    )
    ap.add_argument(
        "--stage1-min-samples",
        type=int,
        default=DEFAULT_STAGE1_MIN_SAMPLES,
    )
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    fig_dir = out / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    labels = animal_sex_condition(args.nor_h5)
    labels.to_csv(out / "animal_labels.csv", index=False)

    flat = pool_flat_prototypes(args.kinematics_csv, chunksize=int(args.chunksize))
    flat = attach_animal_labels(flat, labels)
    flat.to_csv(out / "flat_prototypes.csv", index=False)

    hdb_note = (
        f"HDBSCAN(min_cluster_size={args.min_cluster_size}, "
        f"min_samples={args.min_samples})"
    )

    print("=== flat (all num_states) ===", flush=True)
    flat_fit = flat[flat["n_bouts"] >= int(args.min_bouts)].copy()
    flat_cl, flat_load, flat_sum = run_hdbscan(
        flat_fit,
        min_cluster_size=int(args.min_cluster_size),
        min_samples=int(args.min_samples),
    )
    flat_cl.to_csv(out / "flat_clustered_all_ss.csv", index=False)
    print(
        f"  flat n={flat_sum['n_fit']} clusters={flat_sum['n_clusters']} "
        f"noise={flat_sum['noise_frac']:.3f}",
        flush=True,
    )
    fig_gold_ordination(
        flat_cl,
        flat_load,
        CLUSTER_FEAT_COLS,
        flat_sum["pca_var_ratio"],
        out_stem=fig_dir / "fig_prototype_ordination_flat",
        dest=args.dest,
        mode_label="flat (animal × model × syllable)",
        footnote_extra="Per-animal kpMS alphabets; no within-animal equate.",
        hdbscan_note=hdb_note,
    )

    print("=== stage-1 within-animal, then across (all num_states) ===", flush=True)
    s1, s1_sum = stage1_within_animal_prototypes(
        flat,
        min_cluster_size=int(args.stage1_min_cluster_size),
        min_samples=int(args.stage1_min_samples),
        min_bouts=int(args.min_bouts),
    )
    s1 = attach_animal_labels(s1, labels)
    s1.to_csv(out / "stage1_prototypes_all_ss.csv", index=False)
    s1_cl, s1_load, s1_across = run_hdbscan(
        s1,
        min_cluster_size=int(args.min_cluster_size),
        min_samples=int(args.min_samples),
    )
    s1_cl.to_csv(out / "stage1_clustered_all_ss.csv", index=False)
    print(
        f"  stage1 prototypes={s1_sum['n_stage1_prototypes']} "
        f"(within-clusters={s1_sum['n_within_animal_clusters']}, "
        f"singletons={s1_sum['n_singletons_or_noise']}) -> "
        f"across clusters={s1_across['n_clusters']} "
        f"noise={s1_across['noise_frac']:.3f}",
        flush=True,
    )
    fig_gold_ordination(
        s1_cl,
        s1_load,
        CLUSTER_FEAT_COLS,
        s1_across["pca_var_ratio"],
        out_stem=fig_dir / "fig_prototype_ordination_stage1",
        dest=args.dest,
        mode_label="stage-1 within-animal centroids → across-animal HDBSCAN",
        footnote_extra=(
            f"Stage-1: {s1_sum['n_within_animal_clusters']} within-animal clusters + "
            f"{s1_sum['n_singletons_or_noise']} singletons across {s1_sum['n_animals']} animals "
            f"(within HDBSCAN min_cluster_size={args.stage1_min_cluster_size}, "
            f"min_samples={args.stage1_min_samples})."
        ),
        hdbscan_note=hdb_note,
    )

    run = {
        "kinematics_csv": str(args.kinematics_csv),
        "layout": "2d_pca_all_ss_pooled",
        "min_bouts": int(args.min_bouts),
        "feature_cols": list(CLUSTER_FEAT_COLS),
        "ordinate": "PCA on z-scored CLUSTER_POOL features (not PCoA); all num_states pooled",
        "flat": flat_sum,
        "stage1_within": s1_sum,
        "stage1_across": s1_across,
    }
    (out / "run_summary.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    (out / "INFO_prototype_ordination.md").write_text(
        """# INFO — prototype PCA ordination (flat vs stage-1, all K pooled)

## Question (plain)

Where do per-animal syllable kinematic prototypes sit in feature-space PCA when
clustered flat vs after within-animal stage-1 equating (all `num_states` together)?

## Grain

- Flat: `(animal, model, raw_syllable_id)`, `n_bouts` ≥ 10, all K pooled.
- Stage-1: within-animal HDBSCAN centroid (across that animal's 9 models), then
  across-animal HDBSCAN.

## Ordinate

PCA on the same 9 z-scored kinematic columns used for HDBSCAN (feature-space).
Not PCoA. One PCA per panel (flat / stage-1).

## Association / hit rule

Descriptive (D) only. Color = `cluster_id` (turbo); grey = noise (−1).

## What this is not

Not portable `raw_syllable_id`; not condition / sex I.
""",
        encoding="utf-8",
    )
    (fig_dir / "FIGURES.md").write_text(
        """# Figures — prototype PCA 2D (gold layout)

Dest = slides. D only. All `num_states` pooled.

| Stem | Claim |
|------|-------|
| `fig_prototype_ordination_flat` | Flat animal×model×syllable prototypes in PC1×PC2 + loadings |
| `fig_prototype_ordination_stage1` | Stage-1 within-animal centroids, then across-animal HDBSCAN |

```powershell
uv run python scratch/nor_object_mi/per_animal_prototype_ordination.py
```
""",
        encoding="utf-8",
    )
    print(f"Done -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
