"""Interactive Plotly 3D PCA of soft+shape alphabet-equate feature clouds.

Loads ``prototypes_animal_model_syllable.csv``; feature-set select + checkbox
filters for sex / condition (tx) / session / trial. Marker fill defaults to
HDBSCAN ``cluster_id`` (turbo); toggle to animal-hash. Outline = condition;
symbol = sex.

Regen (after soft-shape runner with session+trial grain):

  uv run python scratch/nor_object_mi/alphabet_equate_soft_shape_plotly3d.py --layout per_animal
  uv run python scratch/nor_object_mi/alphabet_equate_soft_shape_plotly3d.py --layout pooled
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.decomposition import PCA

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from maze.kpms.behavior_ethogram.cluster import zscore_features  # noqa: E402
from nor_object_mi._pub_style import CONDITION_COLOR, CONDITION_ORDER  # noqa: E402
from nor_object_mi.alphabet_equate_soft_shape import (  # noqa: E402
    ACCENT_COLS,
    BASELINE_BOUT_COLS,
    DEFAULT_PER_ANIMAL,
    DEFAULT_POOLED,
    average_over_animals,
    residualize_within_animal,
)
from nor_object_mi.bout_kinematics import SHAPE_FIELDS  # noqa: E402
from nor_object_mi.plotly_strata_filters import (  # noqa: E402
    SESSION_ORDER,
    SEX_ORDER,
    TRIAL_ORDER,
    ordered_present,
    write_html_with_strata_filters,
)

MAX_POINTS_DEFAULT = 12_000


def _proto_path(ensemble: Path) -> Path:
    return (
        ensemble
        / "_nor_object_mi"
        / "alphabet_equate_soft_shape"
        / "prototypes_animal_model_syllable.csv"
    )


def _out_html(ensemble: Path, *, grain: str) -> Path:
    stem = (
        "fig_alphabet_equate_soft_shape_pca3d_avganimal"
        if grain == "avg_animals"
        else "fig_alphabet_equate_soft_shape_pca3d"
    )
    return (
        ensemble
        / "_nor_object_mi"
        / "alphabet_equate_soft_shape"
        / "figures"
        / f"{stem}.html"
    )


def _animal_color_hex(animal_id: str) -> str:
    rng = np.random.default_rng(abs(hash(str(animal_id))) % (2**32))
    rgb = rng.random(3) * 0.7 + 0.15
    return f"#{int(rgb[0] * 255):02x}{int(rgb[1] * 255):02x}{int(rgb[2] * 255):02x}"


def _turbo_hex_lookup(cluster_ids: np.ndarray) -> dict[int, str]:
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors

    pos = sorted({int(x) for x in cluster_ids if int(x) >= 0})
    cmap = plt.get_cmap("turbo")
    lookup = {-1: "#c8c8c8"}
    if not pos:
        return lookup
    for i, cid in enumerate(pos):
        lookup[cid] = mcolors.to_hex(cmap(i / max(len(pos) - 1, 1)))
    return lookup


def _hdbscan_labels(Z: np.ndarray) -> np.ndarray:
    try:
        import hdbscan
    except ImportError:
        return np.full(Z.shape[0], -1, dtype=np.int64)
    cl = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=3, metric="euclidean")
    return np.asarray(cl.fit_predict(Z), dtype=np.int64)


def ordinate_feature_set(
    proto: pd.DataFrame,
    cols: list[str],
    *,
    accent_resid: bool,
) -> tuple[pd.DataFrame, list[float]]:
    df = proto.copy()
    if accent_resid:
        df = residualize_within_animal(df, [c for c in ACCENT_COLS if c in cols])
    X = df[cols].to_numpy(dtype=np.float64)
    ok = np.isfinite(X).all(axis=1)
    df = df.loc[ok].reset_index(drop=True)
    X = X[ok]
    Z, _, _ = zscore_features(X)
    pca = PCA(n_components=min(3, Z.shape[1], Z.shape[0])).fit(Z)
    scores = pca.transform(Z)
    labels = _hdbscan_labels(Z)
    df = df.copy()
    df["pc1"] = scores[:, 0]
    df["pc2"] = scores[:, 1] if scores.shape[1] > 1 else 0.0
    df["pc3"] = scores[:, 2] if scores.shape[1] > 2 else 0.0
    df["cluster_id"] = labels
    var = [float(v) for v in pca.explained_variance_ratio_]
    return df, var


def _subsample(df: pd.DataFrame, max_points: int, *, seed: int = 0) -> pd.DataFrame:
    if len(df) <= max_points:
        return df
    return df.sample(n=max_points, random_state=seed).reset_index(drop=True)


def _stratum_iters(df: pd.DataFrame) -> list[tuple[str, str, str, str]]:
    """Unique (sex, condition, session, trial) with missing strata as ''."""
    has_session = "session" in df.columns
    has_trial = "trial" in df.columns
    rows: list[tuple[str, str, str, str]] = []
    sexes = ordered_present(df["sex"].astype(str), SEX_ORDER) if "sex" in df.columns else [""]
    conds = (
        ordered_present(df["condition"].astype(str), CONDITION_ORDER)
        if "condition" in df.columns
        else [""]
    )
    sessions = (
        ordered_present(df["session"].astype(str), SESSION_ORDER) if has_session else [""]
    )
    trials = ordered_present(df["trial"].astype(str), TRIAL_ORDER) if has_trial else [""]
    for sex in sexes:
        for cond in conds:
            for sess in sessions:
                for trial in trials:
                    rows.append((sex, cond, sess, trial))
    return rows


def _add_traces(
    fig: go.Figure,
    df: pd.DataFrame,
    *,
    tag: str,
    color_bank: list[dict],
) -> int:
    lookup = _turbo_hex_lookup(df["cluster_id"].to_numpy())
    n = 0
    for sex, cond, sess, trial in _stratum_iters(df):
        mask = pd.Series(True, index=df.index)
        if sex:
            mask &= df["sex"].astype(str) == sex
        if cond:
            mask &= df["condition"].astype(str) == cond
        if sess and "session" in df.columns:
            mask &= df["session"].astype(str) == sess
        if trial and "trial" in df.columns:
            mask &= df["trial"].astype(str) == trial
        sub = df.loc[mask]
        if sub.empty:
            continue
        animal_cols = [_animal_color_hex(a) for a in sub["animal_id"].astype(str)]
        cluster_cols = [lookup[int(c)] for c in sub["cluster_id"]]
        symbol = "diamond" if sex == "M" else "circle"
        edge = CONDITION_COLOR.get(cond, "#888888") if cond else "#888888"
        fig.add_trace(
            go.Scatter3d(
                x=sub["pc1"],
                y=sub["pc2"],
                z=sub["pc3"],
                mode="markers",
                name=f"{sex}/{cond}/{sess}/{trial}".strip("/"),
                legendgroup=tag,
                showlegend=False,
                visible=True,
                meta={
                    "tag": tag,
                    "sex": sex,
                    "condition": cond,
                    "session": sess,
                    "trial": trial,
                },
                marker=dict(
                    size=3.5,
                    color=cluster_cols,  # default fill = cluster_id
                    symbol=symbol,
                    opacity=0.75,
                    line=dict(width=1.5, color=edge),
                ),
                customdata=np.column_stack(
                    [
                        sub["animal_id"].astype(str).to_numpy(),
                        sub["cluster_id"].to_numpy(),
                        sub["n_bouts"].to_numpy(),
                        sub["raw_syllable_id"].to_numpy(),
                    ]
                ),
                hovertemplate=(
                    f"{tag}<br>sex={sex or '—'} condition={cond or '—'} "
                    f"session={sess or '—'} trial={trial or '—'}<br>"
                    "animal=%{customdata[0]} cluster=%{customdata[1]} "
                    "n_bouts=%{customdata[2]} syll=%{customdata[3]}<br>"
                    "PC1=%{x:.2f} PC2=%{y:.2f} PC3=%{z:.2f}<extra></extra>"
                ),
            )
        )
        color_bank.append({"animal": animal_cols, "cluster": cluster_cols})
        n += 1
    return n


def build_html(
    panels: list[tuple[str, pd.DataFrame, list[float]]],
    out_html: Path,
    *,
    layout: str,
    n_full: int,
    n_shown: int,
) -> None:
    fig = go.Figure()
    color_bank: list[dict] = []
    tags: list[str] = []
    tag_labels: list[str] = []
    for i, (tag, df, var) in enumerate(panels):
        _add_traces(fig, df, tag=tag, color_bank=color_bank)
        tags.append(tag)
        pc = "/".join(f"{v:.0%}" for v in var[:3])
        tag_labels.append(f"{tag} (PC {pc})")

    # Collect strata present on first panel (same schema for all)
    df0 = panels[0][1]
    sexes = ordered_present(df0["sex"].astype(str), SEX_ORDER) if "sex" in df0.columns else []
    conditions = (
        ordered_present(df0["condition"].astype(str), CONDITION_ORDER)
        if "condition" in df0.columns
        else []
    )
    sessions = (
        ordered_present(df0["session"].astype(str), SESSION_ORDER)
        if "session" in df0.columns
        else []
    )
    trials = (
        ordered_present(df0["trial"].astype(str), TRIAL_ORDER) if "trial" in df0.columns else []
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

    # Extend filter HTML with color-mode select + color bank JS.
    # write_html_with_strata_filters then patch in color mode.
    write_html_with_strata_filters(
        fig,
        out_html,
        tags=tags,
        tag_labels=tag_labels,
        sexes=sexes,
        conditions=conditions,
        sessions=sessions,
        trials=trials,
        title_html=f"Soft+shape feature cloud · {layout}",
        subtitle_html=(
            f"z-score → PCA · n={n_shown}/{n_full} · "
            "default fill=<b>cluster_id</b> (turbo) · outline=condition · F=○ M=◇"
        ),
        color_note=(
            "trial = object step (nvl_obj / id_obj / no_obj); condition = SD arm. "
            "avg_animals grain collapses animal/session/trial before HDBSCAN."
        ),
    )
    _inject_color_mode(out_html, color_bank)


def _inject_color_mode(out_html: Path, color_bank: list[dict]) -> None:
    text = out_html.read_text(encoding="utf-8")
    bank_json = json.dumps(color_bank)
    inject_ctrl = """
  <div class="filt-group">
    <div class="filt-title">marker fill</div>
    <select id="colorMode">
      <option value="cluster" selected>cluster_id (HDBSCAN)</option>
      <option value="animal">animal (hash)</option>
    </select>
  </div>
"""
    text = text.replace(
        '<div class="filt-group">\n    <div class="filt-title">feature set</div>',
        inject_ctrl
        + '<div class="filt-group">\n    <div class="filt-title">feature set</div>',
        1,
    )
    inject_js = f"""
    const COLOR_BANK = {bank_json};
    function applyColorMode() {{
      const gd = document.getElementById('strata3d');
      if (!gd || !gd.data || !COLOR_BANK.length) return;
      const mode = document.getElementById('colorMode').value;
      const colors = COLOR_BANK.map(b => mode === 'animal' ? b.animal : b.cluster);
      Plotly.restyle(gd, {{'marker.color': colors}});
    }}
    document.addEventListener('DOMContentLoaded', () => {{
      const sel = document.getElementById('colorMode');
      if (sel) sel.addEventListener('change', applyColorMode);
    }});
"""
    text = text.replace("<script>", "<script>\n" + inject_js, 1)
    out_html.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--layout", choices=("pooled", "per_animal"), required=True)
    ap.add_argument(
        "--grain",
        choices=("animal_resolved", "avg_animals"),
        default="avg_animals",
        help=(
            "animal_resolved = animal×model×syllable[×session×trial]; "
            "avg_animals = mean over animals → model|stem × syllable (signatures grain)"
        ),
    )
    ap.add_argument("--ensemble-root", type=Path, default=None)
    ap.add_argument("--prototypes-csv", type=Path, default=None)
    ap.add_argument("--out-html", type=Path, default=None)
    ap.add_argument("--min-bouts", type=int, default=3)
    ap.add_argument("--max-points", type=int, default=MAX_POINTS_DEFAULT)
    args = ap.parse_args(argv)

    ensemble = args.ensemble_root or (
        DEFAULT_POOLED if args.layout == "pooled" else DEFAULT_PER_ANIMAL
    )
    proto_csv = args.prototypes_csv or _proto_path(ensemble)
    out_html = args.out_html or _out_html(ensemble, grain=args.grain)
    if not proto_csv.is_file():
        print(f"missing prototypes: {proto_csv}", flush=True)
        return 1

    proto_raw = pd.read_csv(proto_csv)
    feat_cols = list(BASELINE_BOUT_COLS) + list(SHAPE_FIELDS)
    if args.grain == "avg_animals":
        if args.layout == "per_animal":
            print(
                "NOTE: per_animal avg_animals groups by paramscan_stem × syllable "
                "across animals — raw_syllable_id is NOT portable (ADR-0005 foil).",
                flush=True,
            )
        proto = average_over_animals(
            proto_raw,
            feat_cols,
            layout=args.layout,
            min_bouts=int(args.min_bouts),
        )
        out_csv = proto_csv.parent / "prototypes_model_syllable_avganimal.csv"
        proto.to_csv(out_csv, index=False)
        print(f"wrote {out_csv} n={len(proto)}", flush=True)
    else:
        proto = proto_raw.loc[proto_raw["n_bouts"] >= int(args.min_bouts)].reset_index(
            drop=True
        )
        if "session" not in proto.columns or "trial" not in proto.columns:
            print(
                "NOTE: prototypes lack session/trial — re-run alphabet_equate_soft_shape.py "
                "for those checkbox filters. Sex/condition still work.",
                flush=True,
            )

    n_full = len(proto)
    cells: list[tuple[str, list[str], bool]] = [
        ("baseline9", list(BASELINE_BOUT_COLS), False),
        ("baseline9_accent_resid", list(BASELINE_BOUT_COLS), True),
        ("baseline9_shape", feat_cols, False),
        ("baseline9_shape_accent_resid", feat_cols, True),
    ]

    panels: list[tuple[str, pd.DataFrame, list[float]]] = []
    for tag, cols, resid in cells:
        # Accent resid needs multiple animals — skip on avg_animals (single dummy animal).
        if resid and args.grain == "avg_animals":
            print(f"  skip {tag} (accent resid meaningless after avg_animals)", flush=True)
            continue
        df, var = ordinate_feature_set(proto, cols, accent_resid=resid)
        n_cl = int(df.loc[df["cluster_id"] >= 0, "cluster_id"].nunique())
        n_noise = int((df["cluster_id"] < 0).sum())
        df = _subsample(df, int(args.max_points))
        print(
            f"  {tag}: n={len(df)}/{n_full} "
            f"hdbscan_k={n_cl} noise={n_noise} "
            f"PC={['%.0f%%' % (100 * v) for v in var]}",
            flush=True,
        )
        panels.append((tag, df, var))

    if not panels:
        print("no panels to plot", flush=True)
        return 1

    build_html(
        panels,
        out_html,
        layout=f"{args.layout} · {args.grain}",
        n_full=n_full,
        n_shown=len(panels[0][1]),
    )
    print(f"Open: {out_html}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
