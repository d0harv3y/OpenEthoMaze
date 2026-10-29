"""Interactive Plotly 3D PCA for across-animal HDBSCAN (min_cluster_size=4, min_samples=2).

Writes an HTML you can pan/rotate in a browser. Stage-1 within-animal equate first,
then across HDBSCAN at 4/2; flat 4/2 included as a second trace group (dropdown).

Regen:
  uv run python scratch/nor_object_mi/per_animal_prototype_ordination_plotly3d.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from maze.kpms.behavior_ethogram.cluster import zscore_features  # noqa: E402
from nor_object_mi._pub_style import CONDITION_COLOR, CONDITION_ORDER  # noqa: E402
from nor_object_mi.per_animal_prototype_ordination import (  # noqa: E402
    CLUSTER_FEAT_COLS,
    DEFAULT_KIN,
    DEFAULT_NOR,
    DEFAULT_OUT,
    animal_sex_condition,
    attach_animal_labels,
    pca_ordination,
    pool_flat_prototypes,
    run_hdbscan,
    stage1_within_animal_prototypes,
)
from nor_object_mi.plotly_strata_filters import (  # noqa: E402
    SEX_ORDER,
    ordered_present,
    write_html_with_strata_filters,
)

# Across HDBSCAN request
ACROSS_MIN_CLUSTER_SIZE = 4
ACROSS_MIN_SAMPLES = 2
STAGE1_MIN_CLUSTER_SIZE = 2
STAGE1_MIN_SAMPLES = 1


def _turbo_hex(n: int) -> list[str]:
    import matplotlib.pyplot as plt

    cmap = plt.get_cmap("turbo")
    if n <= 1:
        return ["#30123b"]
    return [mcolors_to_hex(cmap(i / max(n - 1, 1))) for i in range(n)]


def mcolors_to_hex(rgba) -> str:
    import matplotlib.colors as mcolors

    return mcolors.to_hex(rgba)


def _cluster_color_map(cluster_ids: pd.Series) -> dict[int, str]:
    pos = sorted(int(x) for x in cluster_ids.unique() if int(x) >= 0)
    hexes = _turbo_hex(len(pos))
    lookup = {cid: hexes[i] for i, cid in enumerate(pos)}
    lookup[-1] = "#c8c8c8"
    return lookup


def _add_mode_traces(fig: go.Figure, cl: pd.DataFrame, *, legendgroup: str) -> int:
    """Add sex×condition traces (fill=cluster_id). Returns number of traces added."""
    lookup = _cluster_color_map(cl["cluster_id"])
    n = 0
    noise = cl[cl["cluster_id"] < 0]
    if not noise.empty:
        fig.add_trace(
            go.Scatter3d(
                x=noise["pc1"],
                y=noise["pc2"],
                z=noise["pc3"],
                mode="markers",
                name=f"{legendgroup} noise",
                legendgroup=legendgroup,
                showlegend=False,
                visible=True,
                meta={
                    "tag": legendgroup,
                    "sex": "",
                    "condition": "",
                    "session": "",
                    "trial": "",
                },
                marker=dict(size=2.5, color="#c8c8c8", opacity=0.35, symbol="circle"),
                hovertemplate=(
                    "noise (−1)<br>PC1=%{x:.2f} PC2=%{y:.2f} PC3=%{z:.2f}"
                    "<extra></extra>"
                ),
            )
        )
        n += 1

    clustered = cl[cl["cluster_id"] >= 0]
    for sex, symbol in (("F", "circle"), ("M", "diamond")):
        for cond in CONDITION_ORDER:
            sub = clustered[
                (clustered["sex"].astype(str) == sex)
                & (clustered["condition"].astype(str) == cond)
            ]
            if sub.empty:
                continue
            colors = [lookup[int(c)] for c in sub["cluster_id"]]
            fig.add_trace(
                go.Scatter3d(
                    x=sub["pc1"],
                    y=sub["pc2"],
                    z=sub["pc3"],
                    mode="markers",
                    name=f"{legendgroup} {sex}/{cond}",
                    legendgroup=legendgroup,
                    showlegend=False,
                    visible=True,
                    meta={
                        "tag": legendgroup,
                        "sex": sex,
                        "condition": cond,
                        "session": "",
                        "trial": "",
                    },
                    marker=dict(
                        size=4.5,
                        color=colors,
                        symbol=symbol,
                        opacity=0.9,
                        line=dict(width=2, color=CONDITION_COLOR[cond]),
                    ),
                    customdata=np.column_stack(
                        [
                            sub["cluster_id"].to_numpy(),
                            sub["animal_id"].astype(str).to_numpy(),
                            sub["n_bouts"].to_numpy(),
                        ]
                    ),
                    hovertemplate=(
                        f"sex={sex} condition={cond}<br>"
                        "cluster=%{customdata[0]} animal=%{customdata[1]} "
                        "n_bouts=%{customdata[2]}<br>"
                        "PC1=%{x:.2f} PC2=%{y:.2f} PC3=%{z:.2f}"
                        "<extra></extra>"
                    ),
                )
            )
            n += 1
    return n


def fit_with_pcs(proto: pd.DataFrame, *, min_cluster_size: int, min_samples: int) -> pd.DataFrame:
    fit, _loadings, summary = run_hdbscan(
        proto,
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
    )
    # run_hdbscan already puts pc1/pc2 from 2D-oriented pca_ordination (full scores).
    # Recompute to ensure pc3 present (scores has all components).
    mat = fit[list(CLUSTER_FEAT_COLS)].to_numpy(dtype=np.float64)
    z, _, _ = zscore_features(mat)
    scores, _load, var = pca_ordination(z)
    fit = fit.copy()
    fit["pc1"] = scores[:, 0]
    fit["pc2"] = scores[:, 1]
    fit["pc3"] = scores[:, 2] if scores.shape[1] > 2 else 0.0
    print(
        f"  n={summary['n_fit']} clusters={summary['n_clusters']} "
        f"noise={summary['noise_frac']:.3f} "
        f"PC var={var[0]:.1%}/{var[1]:.1%}/{var[2]:.1%}",
        flush=True,
    )
    return fit


def build_html(flat_cl: pd.DataFrame, s1_cl: pd.DataFrame, out_html: Path) -> None:
    fig = go.Figure()
    _add_mode_traces(fig, flat_cl, legendgroup="flat")
    _add_mode_traces(fig, s1_cl, legendgroup="stage1")
    sexes = ordered_present(
        pd.concat([flat_cl["sex"], s1_cl["sex"]]).astype(str), SEX_ORDER
    )
    conditions = ordered_present(
        pd.concat([flat_cl["condition"], s1_cl["condition"]]).astype(str),
        CONDITION_ORDER,
    )
    fig.update_layout(
        scene=dict(
            xaxis_title="PC1",
            yaxis_title="PC2",
            zaxis_title="PC3",
            aspectmode="cube",
        ),
        margin=dict(l=0, r=0, t=20, b=0),
        showlegend=False,
    )
    write_html_with_strata_filters(
        fig,
        out_html,
        tags=["stage1", "flat"],
        tag_labels=["stage-1 → across (4/2)", "flat across (4/2)"],
        sexes=sexes,
        conditions=conditions,
        sessions=[],  # prototypes pool across sessions
        trials=[],
        title_html="Across HDBSCAN (min_cluster_size=4, min_samples=2) · PCA 3D",
        subtitle_html="fill=<b>cluster_id</b> (turbo) · outline=condition · F=○ M=◇",
        color_note=(
            "session / trial not on this table (pooled across protocol steps). "
            "Use soft-shape Plotly for those strata."
        ),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kinematics-csv", type=Path, default=DEFAULT_KIN)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--chunksize", type=int, default=250_000)
    ap.add_argument("--min-bouts", type=int, default=10)
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    labels = animal_sex_condition(args.nor_h5)
    flat = pool_flat_prototypes(args.kinematics_csv, chunksize=int(args.chunksize))
    flat = attach_animal_labels(flat, labels)
    flat_fit = flat[flat["n_bouts"] >= int(args.min_bouts)].copy()

    print("=== flat across HDBSCAN 4/2 ===", flush=True)
    flat_cl = fit_with_pcs(
        flat_fit,
        min_cluster_size=ACROSS_MIN_CLUSTER_SIZE,
        min_samples=ACROSS_MIN_SAMPLES,
    )
    flat_cl.to_csv(out / "flat_clustered_all_ss_mcs4_ms2.csv", index=False)

    print("=== stage-1 then across HDBSCAN 4/2 ===", flush=True)
    s1, s1_sum = stage1_within_animal_prototypes(
        flat,
        min_cluster_size=STAGE1_MIN_CLUSTER_SIZE,
        min_samples=STAGE1_MIN_SAMPLES,
        min_bouts=int(args.min_bouts),
    )
    s1 = attach_animal_labels(s1, labels)
    print(
        f"  stage1 prototypes={s1_sum['n_stage1_prototypes']} "
        f"(within-clusters={s1_sum['n_within_animal_clusters']}, "
        f"singletons={s1_sum['n_singletons_or_noise']})",
        flush=True,
    )
    s1_cl = fit_with_pcs(
        s1,
        min_cluster_size=ACROSS_MIN_CLUSTER_SIZE,
        min_samples=ACROSS_MIN_SAMPLES,
    )
    s1_cl.to_csv(out / "stage1_clustered_all_ss_mcs4_ms2.csv", index=False)

    html = out / "figures" / "prototype_pca3d_across_mcs4_ms2.html"
    build_html(flat_cl, s1_cl, html)
    print(f"Open: {html}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
