"""Syllable descriptives for az-sd-vast_paramscan2026 (27 kpMS fits).

Same fig1–5 layout as ``moseq_251017/_syllable_descriptives/regen_descriptives.py``,
adapted for fixed ``kappa1=1e8`` and a third axis ``conf_threshold`` (ct).

Grid: k2 ∈ {1e4, 3e4, 1e5} × K ∈ {50, 75, 100} × ct ∈ {0.1, 0.2, 0.3} = 27.

Regen (OpenEthoMaze repo root):

  uv run python scratch/vast_moseq/regen_paramscan2026_descriptives.py
  uv run python scratch/vast_moseq/regen_paramscan2026_descriptives.py --figures-only
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import colormaps
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.syllable_cleanup import maybe_absorb_short_bouts  # noqa: E402

DEFAULT_ENSEMBLE = Path(r"D:\az-sd-vast_paramscan2026\anatomical")
DEFAULT_OUT = Path(r"D:\az-sd-vast_paramscan2026\_syllable_descriptives")
MIN_BOUT = 3
SOURCE_TAG = "az-sd-vast_paramscan2026"

_MODEL_RE = re.compile(
    r"^paramscan_s1-([^_]+)_s2-([^_]+)_ss-(\d+)(?:_ct-([0-9.eE+-]+))?$"
)

K2_COLORS = {"1e4": "#a8dadc", "3e4": "#457b9d", "1e5": "#1d3557"}
K2_ORD = {"1e4": 0, "3e4": 1, "1e5": 2}
CT_ORD = {"0.1": 0, "0.2": 1, "0.3": 2}
CT_LINESTYLES = {"0.1": "-", "0.2": "--", "0.3": ":"}

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    }
)


def parse_model(name: str) -> dict[str, object]:
    m = _MODEL_RE.match(name)
    if m is None:
        raise ValueError(f"unrecognized model name: {name!r}")
    k1, k2, k_s, ct = m.group(1), m.group(2), m.group(3), m.group(4)
    K = int(k_s)
    ct_s = ct if ct is not None else ""
    label = f"k2={k2}  ct={ct_s}  K={K}" if ct_s else f"k2={k2}  K={K}"
    return {
        "model": name,
        "kappa1": k1,
        "kappa2": k2,
        "K": K,
        "ct": ct_s,
        "label": label,
    }


def rle(z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if z.size == 0:
        empty = np.empty(0, np.int64)
        return empty, empty, empty
    ch = np.flatnonzero(z[1:] != z[:-1]) + 1
    starts = np.concatenate(([0], ch))
    ends = np.concatenate((ch, [z.size]))
    return z[starts].astype(np.int64), (ends - starts).astype(np.int64), starts


def summarize_model(path: Path, cleanup: bool):
    syll_bout_counts: dict[int, int] = {}
    syll_frame_counts: dict[int, int] = {}
    syll_durs: dict[int, list[int]] = {}
    all_durs: list[np.ndarray] = []
    n_rec = 0
    n_frames_tot = 0
    with h5py.File(path, "r") as f:
        for key in f.keys():
            z = np.asarray(f[key]["syllable"], dtype=np.int64)
            if cleanup:
                z = maybe_absorb_short_bouts(z, MIN_BOUT)
            n_rec += 1
            n_frames_tot += z.size
            labels, durs, _ = rle(z)
            all_durs.append(durs)
            for lab, dur in zip(labels.tolist(), durs.tolist()):
                syll_bout_counts[lab] = syll_bout_counts.get(lab, 0) + 1
                syll_frame_counts[lab] = syll_frame_counts.get(lab, 0) + int(dur)
                syll_durs.setdefault(lab, []).append(int(dur))
    d = np.concatenate(all_durs) if all_durs else np.empty(0, np.int64)
    used = sorted(syll_bout_counts)
    ranked = sorted(used, key=lambda s: (-syll_bout_counts[s], s))
    rank_of = {s: r for r, s in enumerate(ranked)}
    count_rows = []
    for s in used:
        count_rows.append(
            {
                "syllable": int(s),
                "freq_rank": int(rank_of[s]),
                "n_bouts": int(syll_bout_counts[s]),
                "n_frames": int(syll_frame_counts[s]),
                "occupancy": (
                    syll_frame_counts[s] / n_frames_tot if n_frames_tot else 0.0
                ),
                "median_bout_frames": float(np.median(syll_durs[s])),
                "mean_bout_frames": float(np.mean(syll_durs[s])),
                "p25_bout_frames": float(np.percentile(syll_durs[s], 25)),
                "p75_bout_frames": float(np.percentile(syll_durs[s], 75)),
                "p90_bout_frames": float(np.percentile(syll_durs[s], 90)),
            }
        )
    model_row = {
        "n_recordings": n_rec,
        "n_frames": n_frames_tot,
        "n_syllables_used": len(used),
        "n_bouts": int(d.size),
        "median_bout_frames": float(np.median(d)) if d.size else np.nan,
        "mean_bout_frames": float(np.mean(d)) if d.size else np.nan,
        "p10_bout_frames": float(np.percentile(d, 10)) if d.size else np.nan,
        "p25_bout_frames": float(np.percentile(d, 25)) if d.size else np.nan,
        "p75_bout_frames": float(np.percentile(d, 75)) if d.size else np.nan,
        "p90_bout_frames": float(np.percentile(d, 90)) if d.size else np.nan,
        "frac_1frame": float(np.mean(d == 1)) if d.size else np.nan,
        "frac_lt_min": float(np.mean(d < MIN_BOUT)) if d.size else np.nan,
        "frac_ge3": float(np.mean(d >= 3)) if d.size else np.nan,
        "frac_ge5": float(np.mean(d >= 5)) if d.size else np.nan,
    }
    if d.size > 200_000:
        rng = np.random.default_rng(0)
        d_sub = rng.choice(d, size=200_000, replace=False)
    else:
        d_sub = d
    return model_row, count_rows, d_sub


def sort_models(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_k2"] = out["kappa2"].map(K2_ORD)
    out["_ct"] = out["ct"].map(CT_ORD).fillna(0)
    out = out.sort_values(["_k2", "_ct", "K"]).drop(columns=["_k2", "_ct"])
    return out.reset_index(drop=True)


def discover_models(ensemble: Path) -> list[Path]:
    return sorted(
        p
        for p in ensemble.iterdir()
        if p.is_dir() and p.name.startswith("paramscan_") and (p / "results.h5").is_file()
    )


def extract_all(
    ensemble: Path,
    out: Path,
    *,
    exclude_ct: set[str] | None = None,
) -> None:
    models = discover_models(ensemble)
    exclude_ct = exclude_ct or set()
    if exclude_ct:
        kept: list[Path] = []
        for mdir in models:
            meta = parse_model(mdir.name)
            if str(meta["ct"]) in exclude_ct:
                continue
            kept.append(mdir)
        models = kept
    print(
        f"n_models={len(models)} MIN_BOUT={MIN_BOUT} exclude_ct={sorted(exclude_ct)} "
        f"ensemble={ensemble}",
        flush=True,
    )
    if not models:
        raise SystemExit(f"no paramscan_*/results.h5 under {ensemble}")
    for cleanup, tag in [(False, "raw"), (True, "clean")]:
        print(f"=== {tag} ===", flush=True)
        model_rows: list[dict] = []
        count_rows: list[dict] = []
        dur_map: dict[str, np.ndarray] = {}
        for i, mdir in enumerate(models, 1):
            meta = parse_model(mdir.name)
            print(f"[{i}/{len(models)}] {tag} {mdir.name}", flush=True)
            mrow, crows, d_sub = summarize_model(mdir / "results.h5", cleanup=cleanup)
            model_rows.append({**meta, **mrow})
            for cr in crows:
                count_rows.append({**meta, **cr})
            dur_map[mdir.name] = d_sub
        model_df = sort_models(pd.DataFrame(model_rows))
        count_df = pd.DataFrame(count_rows)
        model_df.to_csv(out / f"model_summary_{tag}.csv", index=False)
        count_df.to_csv(out / f"syllable_counts_{tag}.csv", index=False)
        np.savez_compressed(out / f"duration_subsamples_{tag}.npz", **dur_map)
        if tag == "raw":
            model_df.to_csv(out / "model_summary.csv", index=False)
            count_df.to_csv(out / "syllable_counts.csv", index=False)
            np.savez_compressed(out / "duration_subsamples.npz", **dur_map)
        cols = [
            "label",
            "n_syllables_used",
            "n_bouts",
            "median_bout_frames",
            "mean_bout_frames",
            "frac_1frame",
            "frac_lt_min",
        ]
        print(model_df[cols].to_string(index=False), flush=True)


def _order_and_labels(model_df: pd.DataFrame) -> tuple[list[str], dict[str, str]]:
    order = model_df["model"].tolist()
    label_map = dict(zip(model_df["model"], model_df["label"]))
    return order, label_map


def _save(fig, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    for ext in (".png", ".pdf", ".svg"):
        fig.savefig(stem.with_suffix(ext))
        print(f"wrote {stem.with_suffix(ext)}", flush=True)
    plt.close(fig)


def fig_stacked_counts(model_df: pd.DataFrame, count_df: pd.DataFrame, tag: str, out: Path) -> None:
    order, label_map = _order_and_labels(model_df)
    max_rank = int(count_df["freq_rank"].max())
    mat = np.zeros((len(order), max_rank + 1))
    for _, r in count_df.iterrows():
        mat[order.index(r["model"]), int(r["freq_rank"])] += r["n_bouts"]
    y = np.arange(len(order))
    cmap = colormaps["viridis"]
    norm = Normalize(vmin=0, vmax=max_rank)
    fig_h = max(7.4, 0.28 * len(order) + 2.0)
    fig, ax = plt.subplots(figsize=(9.2, fig_h))
    left = np.zeros(len(order))
    for rank in range(max_rank + 1):
        vals = mat[:, rank]
        if vals.sum() == 0:
            continue
        ax.barh(y, vals, left=left, height=0.82, color=cmap(norm(rank)), edgecolor="none")
        left += vals
    ax.set_yticks(y)
    ax.set_yticklabels([label_map[m] for m in order], fontsize=7.5)
    ax.set_xlabel("Syllable bout count (all recordings)")
    ax.set_ylabel("Model (k1 fixed 1e8; k2=stage2_kappa, ct=conf_threshold, K=num_states)")
    title = "Syllable bout inventory by frequency rank"
    if tag == "clean":
        title += f" (short-bout absorb <{MIN_BOUT} frames)"
    ax.set_title(title)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Frequency rank (0 = most used)")
    for i in range(len(order)):
        tot = mat[i].sum()
        ax.text(
            tot * 1.01,
            i,
            f"{tot / 1e3:.0f}k",
            va="center",
            ha="left",
            fontsize=7,
            color="#444",
        )
    ax.set_xlim(0, mat.sum(1).max() * 1.14)
    fig.text(
        0.01,
        0.005,
        f"Source: {SOURCE_TAG} results.h5 · stacks by within-model frequency rank · "
        f"~1993 recordings/model · 27 fits",
        fontsize=7,
        color="#555",
    )
    stem = f"fig1_stacked_bout_counts_{tag}" if tag != "raw" else "fig1_stacked_bout_counts"
    _save(fig, out / stem)


def fig_duration_box(model_df: pd.DataFrame, durs, tag: str, out: Path) -> None:
    order, label_map = _order_and_labels(model_df)
    y = np.arange(len(order))
    data = [durs[m] for m in order]
    fig_h = max(7.4, 0.28 * len(order) + 2.0)
    fig, ax = plt.subplots(figsize=(9.2, fig_h))
    bp = ax.boxplot(
        data,
        vert=False,
        positions=y,
        widths=0.65,
        showfliers=False,
        patch_artist=True,
        medianprops=dict(color="black", lw=1.2),
        whiskerprops=dict(color="#444"),
        capprops=dict(color="#444"),
        boxprops=dict(edgecolor="#444", lw=0.8),
    )
    for i, m in enumerate(order):
        k2 = model_df.loc[model_df.model == m, "kappa2"].iloc[0]
        bp["boxes"][i].set_facecolor(K2_COLORS[k2])
    ax.set_yticks(y)
    ax.set_yticklabels([label_map[m] for m in order], fontsize=7.5)
    ax.set_xlabel("Bout duration (frames)")
    ax.set_ylabel("Model")
    title = "Pooled syllable bout duration by model"
    if tag == "clean":
        title += f" (absorb <{MIN_BOUT} frames)"
    ax.set_title(title)
    ax.set_xscale("log")
    ax.legend(
        handles=[
            Patch(facecolor=c, edgecolor="#444", label=f"k2={k}")
            for k, c in K2_COLORS.items()
        ],
        title="stage2_kappa",
        loc="lower right",
        frameon=False,
    )
    fig.text(
        0.01,
        0.005,
        f"Source: {SOURCE_TAG} · subsampled ≤200k bouts/model · outliers hidden · log x · frames",
        fontsize=7,
        color="#555",
    )
    stem = (
        f"fig2_bout_duration_boxplot_{tag}" if tag != "raw" else "fig2_bout_duration_boxplot"
    )
    _save(fig, out / stem)


def fig_ecdf(model_df: pd.DataFrame, durs, tag: str, out: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.8), sharey=True)
    for ax, K in zip(axes, [50, 75, 100]):
        sub = model_df[model_df.K == K]
        for _, row in sub.iterrows():
            d = np.sort(durs[row["model"]])
            yv = np.linspace(0, 1, d.size, endpoint=False)
            ax.plot(
                d,
                yv,
                color=K2_COLORS[row["kappa2"]],
                ls=CT_LINESTYLES.get(str(row["ct"]), "-"),
                alpha=0.85,
                lw=1.1,
            )
        ax.set_xscale("log")
        ax.set_xlabel("Bout duration (frames)")
        ax.set_title(f"K={K}")
        ax.set_xlim(1, 200)
    axes[0].set_ylabel("ECDF")
    legend_handles = [
        Patch(facecolor=c, edgecolor="#444", label=f"k2={k}") for k, c in K2_COLORS.items()
    ] + [
        Line2D([0], [0], color="#333", ls=ls, label=f"ct={ct}")
        for ct, ls in CT_LINESTYLES.items()
    ]
    axes[-1].legend(handles=legend_handles, frameon=False, fontsize=7.5, loc="lower right")
    title = "Bout-duration ECDFs by state-space size K"
    if tag == "clean":
        title += f" (absorb <{MIN_BOUT})"
    fig.suptitle(title, y=1.02)
    fig.text(0.01, -0.02, f"Source: {SOURCE_TAG} · frames", fontsize=7, color="#555")
    fig.tight_layout()
    stem = f"fig3_bout_duration_ecdf_{tag}" if tag != "raw" else "fig3_bout_duration_ecdf"
    _save(fig, out / stem)


def fig_heatmaps_by_K(
    model_df: pd.DataFrame,
    count_df: pd.DataFrame,
    tag: str,
    out: Path,
    vmax: float | None = None,
) -> None:
    if vmax is None:
        vmax = float(np.percentile(count_df["median_bout_frames"], 95))
        vmax = max(20.0, round(vmax))
    for K in [50, 75, 100]:
        sub_m = model_df[model_df.K == K].copy()
        if sub_m.empty:
            continue
        order = sub_m["model"].tolist()
        label_map = dict(zip(sub_m["model"], sub_m["label"]))
        sub_c = count_df[count_df["model"].isin(order)]
        n_ranks = int(sub_c["freq_rank"].max()) + 1
        heat = np.full((len(order), n_ranks), np.nan)
        for _, r in sub_c.iterrows():
            heat[order.index(r["model"]), int(r["freq_rank"])] = r["median_bout_frames"]
        fig_w = max(8.0, 0.11 * n_ranks + 3.5)
        fig, ax = plt.subplots(figsize=(fig_w, max(3.5, 0.42 * len(order) + 1.5)))
        im = ax.imshow(
            heat,
            aspect="auto",
            cmap="magma",
            interpolation="nearest",
            vmin=0,
            vmax=vmax,
        )
        ax.set_yticks(range(len(order)))
        ax.set_yticklabels([label_map[m] for m in order], fontsize=8)
        xt = list(range(0, n_ranks, 5))
        if (n_ranks - 1) not in xt:
            xt.append(n_ranks - 1)
        ax.set_xticks(xt)
        ax.set_xticklabels([str(t) for t in xt])
        ax.set_xlabel("Frequency rank (0 = most used)")
        ax.set_ylabel("Model")
        title = f"Median bout duration (frames) — all syllables · K={K}"
        if tag == "clean":
            title += f" · absorb <{MIN_BOUT}"
        ax.set_title(title)
        cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
        cbar.set_label(f"Median bout duration (frames; color clipped at {vmax:g})")
        fig.text(
            0.01,
            0.005,
            f"Source: {SOURCE_TAG} · within-model frequency rank · frames · shared vmax",
            fontsize=7,
            color="#555",
        )
        stem = f"fig5_median_duration_heatmap_K{K}_{tag}"
        if tag == "raw":
            stem = f"fig5_median_duration_heatmap_K{K}"
        _save(fig, out / stem)


def fig_inventory_scatter(model_df: pd.DataFrame, tag: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.4, 4.4))
    for _, row in model_df.iterrows():
        ax.scatter(
            row["n_syllables_used"],
            row["median_bout_frames"],
            s=40 + (row["K"] - 50) * 1.2,
            color=K2_COLORS[row["kappa2"]],
            edgecolors="white",
            lw=0.5,
            zorder=3,
            marker={"0.1": "o", "0.2": "s", "0.3": "^"}.get(str(row["ct"]), "o"),
        )
    ax.set_xlabel("Syllables used (of K)")
    ax.set_ylabel("Median bout duration (frames)")
    title = "Segmentation grain vs syllable inventory"
    if tag == "clean":
        title += f" (absorb <{MIN_BOUT})"
    ax.set_title(title)
    ax.legend(
        handles=[
            Patch(facecolor=c, edgecolor="#444", label=f"k2={k}") for k, c in K2_COLORS.items()
        ]
        + [
            Line2D(
                [0],
                [0],
                marker=m,
                color="w",
                markerfacecolor="#333",
                markersize=7,
                label=f"ct={ct}",
                linestyle="None",
            )
            for ct, m in (("0.1", "o"), ("0.2", "s"), ("0.3", "^"))
        ],
        frameon=False,
        title="stage2_kappa / ct",
        fontsize=8,
    )
    fig.text(
        0.01,
        -0.02,
        f"Source: {SOURCE_TAG} · marker size ~ K · frames",
        fontsize=7,
        color="#555",
    )
    stem = (
        f"fig4_inventory_vs_median_duration_{tag}"
        if tag != "raw"
        else "fig4_inventory_vs_median_duration"
    )
    _save(fig, out / stem)


def make_figures(
    tag: str,
    out: Path,
    heatmap_vmax: float | None = None,
    *,
    exclude_ct: set[str] | None = None,
) -> None:
    model_df = pd.read_csv(
        out / f"model_summary_{tag}.csv", dtype={"kappa1": str, "kappa2": str, "ct": str}
    )
    count_df = pd.read_csv(out / f"syllable_counts_{tag}.csv", dtype={"ct": str})
    durs = np.load(out / f"duration_subsamples_{tag}.npz")
    exclude_ct = exclude_ct or set()
    if exclude_ct:
        model_df = model_df[~model_df["ct"].isin(exclude_ct)].reset_index(drop=True)
        count_df = count_df[~count_df["ct"].isin(exclude_ct)].reset_index(drop=True)
        print(f"figures for {tag} (dropped ct={sorted(exclude_ct)}; n={len(model_df)})", flush=True)
    else:
        print(f"figures for {tag}", flush=True)
    fig_stacked_counts(model_df, count_df, tag, out)
    fig_duration_box(model_df, durs, tag, out)
    fig_ecdf(model_df, durs, tag, out)
    fig_inventory_scatter(model_df, tag, out)
    fig_heatmaps_by_K(model_df, count_df, tag, out, vmax=heatmap_vmax)


def write_cleanup_note(out: Path) -> None:
    note = out / "cleanup_rule.txt"
    note.write_text(
        "\n".join(
            [
                "Syllable bout cleanup (no frames discarded)",
                f"min_bout_frames = {MIN_BOUT}",
                "",
                "Rule: iteratively absorb any bout shorter than min_bout_frames by",
                "reassigning those frames to a neighbor (same as moseq_251017).",
                "",
                "Labels: k1 = stage1_kappa (fixed 1e8), k2 = stage2_kappa,",
                "K = num_states, ct = conf_threshold from paramscan naming.",
                "As kappa2 -> down, expect more bouts with shorter durations.",
            ]
        ),
        encoding="utf-8",
    )


def write_campaign_readme(out: Path) -> None:
    text = f"""# Syllable descriptives — {SOURCE_TAG}

27 kpMS (keypoint-MoSeq) fits on disk; **default figures drop ct=0.1**
(18 models: k2 × K × {0.2, 0.3}). Fixed `kappa1=1e8`.

| Axis | Values |
|------|--------|
| k2 (stage2 stickiness) | 1e4, 3e4, 1e5 |
| K (num_states) | 50, 75, 100 |
| ct (conf_threshold) | 0.2, 0.3 (0.1 dropped; 0.3 optional later) |

## Figures (clean = absorb bouts <{MIN_BOUT} frames)

| Stem | Slide role |
|------|------------|
| `fig1_stacked_bout_counts_clean` | Bout inventory by frequency rank |
| `fig2_bout_duration_boxplot_clean` | Pooled bout duration by model (color = k2) |
| `fig3_bout_duration_ecdf_clean` | ECDFs by K (color = k2, linestyle = ct) |
| `fig4_inventory_vs_median_duration_clean` | Syllables used vs median duration |
| `fig5_median_duration_heatmap_K{{50,75,100}}_clean` | Median duration × frequency rank |

## Regen

```powershell
uv run python scratch/vast_moseq/regen_paramscan2026_descriptives.py --figures-only --exclude-ct 0.1
uv run python scratch/vast_moseq/regen_paramscan2026_kinematics.py
```

## Next (HDBSCAN slides)

`_syllable_bout_kinematics/` → pool → `_syllable_signatures/` (9-D HDBSCAN).
"""
    (out / "README.md").write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ensemble", type=Path, default=DEFAULT_ENSEMBLE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--figures-only",
        action="store_true",
        help="Skip H5 extract; redraw from existing CSVs / npz",
    )
    ap.add_argument(
        "--exclude-ct",
        type=str,
        default="",
        help="Comma-separated conf_threshold values to drop (e.g. 0.1 or 0.1,0.3)",
    )
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    exclude_ct = {x.strip() for x in str(args.exclude_ct).split(",") if x.strip()}
    write_campaign_readme(out)

    if not args.figures_only:
        extract_all(args.ensemble, out, exclude_ct=exclude_ct)
        write_cleanup_note(out)

    raw_counts = pd.read_csv(out / "syllable_counts_raw.csv", dtype={"ct": str})
    if exclude_ct:
        raw_counts = raw_counts[~raw_counts["ct"].isin(exclude_ct)]
    shared_vmax = float(np.percentile(raw_counts["median_bout_frames"], 95))
    shared_vmax = max(20.0, round(shared_vmax))
    print(f"heatmap shared vmax={shared_vmax} exclude_ct={sorted(exclude_ct)}", flush=True)
    make_figures("raw", out, heatmap_vmax=shared_vmax, exclude_ct=exclude_ct)
    make_figures("clean", out, heatmap_vmax=shared_vmax, exclude_ct=exclude_ct)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
