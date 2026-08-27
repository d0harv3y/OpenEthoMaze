"""Syllable-style descriptives pack for impress n-gram mines (frames).

Reads ``_ngram_mine/<model>/{raw,clean}/ngram_counts.csv`` and writes figures to
``_ngram_descriptives/`` mirroring ``_syllable_descriptives`` layout.

Optional span ECDFs/boxplots resample occurrence spans from ``results.h5``
for selected n (default 2 and 3).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import colormaps
from matplotlib.colors import Normalize
from matplotlib.patches import Patch

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
    }
)

K2_COLORS = {"1e4": "#a8dadc", "3e4": "#457b9d", "1e5": "#1d3557"}
K2_ORD = {"1e4": 0, "3e4": 1, "1e5": 2}
K1_ORD = {"1e6": 0, "1e7": 1, "1e8": 2}


def parse_model(name: str) -> dict:
    m = re.match(r"paramscan_s1-([^_]+)_s2-([^_]+)_ss-(\d+)$", name)
    if not m:
        raise ValueError(name)
    k1, k2, K = m.group(1), m.group(2), int(m.group(3))
    return {
        "model": name,
        "kappa1": k1,
        "kappa2": k2,
        "K": K,
        "label": f"k1={k1}  k2={k2}  K={K}",
    }


def sort_models(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_k2"] = out["kappa2"].map(K2_ORD)
    out["_k1"] = out["kappa1"].map(K1_ORD)
    return out.sort_values(["_k2", "_k1", "K"]).drop(columns=["_k2", "_k1"]).reset_index(drop=True)


def load_counts(mine_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict] = []
    meta_rows: list[dict] = []
    for model_dir in sorted(mine_root.iterdir()):
        if not model_dir.is_dir() or not model_dir.name.startswith("paramscan_"):
            continue
        meta = parse_model(model_dir.name)
        for tag in ("raw", "clean"):
            path = model_dir / tag / "ngram_counts.csv"
            if not path.exists():
                continue
            df = pd.read_csv(path)
            for n, sub in df.groupby("pattern_len"):
                sub = sub.sort_values("count", ascending=False).reset_index(drop=True)
                sub = sub.assign(
                    model=meta["model"],
                    tag=tag,
                    kappa1=meta["kappa1"],
                    kappa2=meta["kappa2"],
                    K=meta["K"],
                    label=meta["label"],
                    freq_rank=np.arange(len(sub)),
                )
                rows.append(sub)
                meta_rows.append(
                    {
                        **meta,
                        "tag": tag,
                        "pattern_len": int(n),
                        "n_patterns": int(len(sub)),
                        "n_occ": int(sub["count"].sum()),
                        "median_span": float(sub["mean_span_frames"].median()),
                        "median_count": float(sub["count"].median()),
                    }
                )
    counts = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    summary = pd.DataFrame(meta_rows)
    return counts, summary


def _save(fig: plt.Figure, out: Path, stem: str) -> None:
    fig.savefig(out / f"{stem}.png")
    fig.savefig(out / f"{stem}.pdf")
    plt.close(fig)
    print(f"wrote {stem}", flush=True)


def fig_stacked_counts(
    counts: pd.DataFrame,
    *,
    pattern_len: int,
    tag: str,
    out: Path,
    max_display_ranks: int = 80,
) -> None:
    sub = counts[(counts.pattern_len == pattern_len) & (counts.tag == tag)].copy()
    if sub.empty:
        return
    models = sort_models(sub[["model", "kappa1", "kappa2", "K", "label"]].drop_duplicates())
    order = models["model"].tolist()
    label_map = dict(zip(models["model"], models["label"]))
    # Keep figure tractable: top ranks colored individually; lump the long tail.
    n_show = min(int(sub["freq_rank"].max()) + 1, int(max_display_ranks))
    model_to_i = {m: i for i, m in enumerate(order)}
    mat = np.zeros((len(order), n_show + 1))  # last col = tail
    mi = sub["model"].map(model_to_i).to_numpy()
    fr = sub["freq_rank"].to_numpy(dtype=np.int64)
    ct = sub["count"].to_numpy(dtype=np.float64)
    in_show = fr < n_show
    np.add.at(mat, (mi[in_show], fr[in_show]), ct[in_show])
    np.add.at(mat, (mi[~in_show], np.full((~in_show).sum(), n_show, dtype=np.int64)), ct[~in_show])
    y = np.arange(len(order))
    cmap = colormaps["viridis"]
    norm = Normalize(vmin=0, vmax=max(n_show - 1, 1))
    fig, ax = plt.subplots(figsize=(8.8, 7.4))
    left = np.zeros(len(order))
    for rank in range(n_show):
        vals = mat[:, rank]
        if vals.sum() == 0:
            continue
        ax.barh(y, vals, left=left, height=0.82, color=cmap(norm(rank)), edgecolor="none")
        left += vals
    tail = mat[:, n_show]
    if tail.sum() > 0:
        ax.barh(y, tail, left=left, height=0.82, color="#bbbbbb", edgecolor="none")
        left += tail
    ax.set_yticks(y)
    ax.set_yticklabels([label_map[m] for m in order])
    ax.set_xlabel("N-gram occurrence count (all recordings)")
    ax.set_ylabel("Model (k1=stage1_kappa, k2=stage2_kappa, K=num_states)")
    title = f"N-gram inventory by frequency rank · n={pattern_len} · {tag}"
    ax.set_title(title)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label(f"Frequency rank (0 = most used; gray = rank≥{n_show})")
    for i in range(len(order)):
        tot = mat[i].sum()
        ax.text(tot * 1.01, i, f"{tot / 1e3:.0f}k", va="center", ha="left", fontsize=7, color="#444")
    ax.set_xlim(0, mat.sum(1).max() * 1.14)
    fig.text(
        0.01,
        0.005,
        "Source: _ngram_mine ngram_counts.csv · stacks by within-model frequency rank · frames",
        fontsize=7,
        color="#555",
    )
    _save(fig, out, f"fig1_stacked_ngram_counts_n{pattern_len}_{tag}")


def fig_heatmap_by_K(
    counts: pd.DataFrame,
    *,
    pattern_len: int,
    tag: str,
    out: Path,
    vmax: float | None = None,
    max_ranks: int | None = None,
) -> None:
    sub = counts[(counts.pattern_len == pattern_len) & (counts.tag == tag)].copy()
    if sub.empty:
        return
    if vmax is None:
        vmax = float(np.percentile(sub["mean_span_frames"], 95))
        vmax = max(20.0, round(vmax))
    for K in [50, 75, 100]:
        models = sort_models(
            sub[sub.K == K][["model", "kappa1", "kappa2", "K", "label"]].drop_duplicates()
        )
        if models.empty:
            continue
        order = models["model"].tolist()
        label_map = dict(zip(models["model"], models["label"]))
        sub_k = sub[sub.model.isin(order)]
        n_ranks = int(sub_k["freq_rank"].max()) + 1
        if max_ranks is not None:
            n_ranks = min(n_ranks, int(max_ranks))
        heat = np.full((len(order), n_ranks), np.nan)
        model_to_i = {m: i for i, m in enumerate(order)}
        mi = sub_k["model"].map(model_to_i).to_numpy()
        fr = sub_k["freq_rank"].to_numpy(dtype=np.int64)
        sp = sub_k["mean_span_frames"].to_numpy(dtype=np.float64)
        keep = fr < n_ranks
        heat[mi[keep], fr[keep]] = sp[keep]
        fig_w = max(8.0, 0.09 * n_ranks + 3.5)
        fig, ax = plt.subplots(figsize=(fig_w, max(3.2, 0.45 * len(order) + 1.5)))
        im = ax.imshow(
            heat, aspect="auto", cmap="magma", interpolation="nearest", vmin=0, vmax=vmax
        )
        ax.set_yticks(range(len(order)))
        ax.set_yticklabels([label_map[m] for m in order], fontsize=8)
        step = 5 if n_ranks <= 80 else 10
        xt = list(range(0, n_ranks, step))
        if (n_ranks - 1) not in xt:
            xt.append(n_ranks - 1)
        ax.set_xticks(xt)
        ax.set_xticklabels([str(t) for t in xt])
        ax.set_xlabel("Frequency rank (0 = most used)")
        ax.set_ylabel("Model")
        ax.set_title(
            f"Mean n-gram span (frames) · n={pattern_len} · K={K} · {tag}"
        )
        cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
        cbar.set_label(f"Mean span frames (color clipped at {vmax:g})")
        fig.text(
            0.01,
            0.005,
            "Source: ngram_counts mean_span_frames · within-model frequency rank",
            fontsize=7,
            color="#555",
        )
        stem = f"fig5_mean_span_heatmap_n{pattern_len}_K{K}_{tag}"
        _save(fig, out, stem)


def fig_inventory_scatter(summary: pd.DataFrame, *, pattern_len: int, tag: str, out: Path) -> None:
    sub = summary[(summary.pattern_len == pattern_len) & (summary.tag == tag)]
    if sub.empty:
        return
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    for _, row in sub.iterrows():
        ax.scatter(
            row["n_patterns"],
            row["median_span"],
            s=40 + (row["K"] - 50) * 1.2,
            color=K2_COLORS[row["kappa2"]],
            edgecolors="white",
            lw=0.5,
            zorder=3,
        )
    ax.set_xlabel("Unique n-gram patterns (count>=2)")
    ax.set_ylabel("Median mean_span_frames")
    ax.set_title(f"Inventory vs typical span · n={pattern_len} · {tag}")
    ax.legend(
        handles=[
            Patch(facecolor=c, edgecolor="#444", label=f"k2={k}") for k, c in K2_COLORS.items()
        ],
        frameon=False,
        title="stage2_kappa",
    )
    fig.text(0.01, -0.02, "Source: _ngram_mine · marker size ~ K", fontsize=7, color="#555")
    _save(fig, out, f"fig4_inventory_vs_span_n{pattern_len}_{tag}")


def fig_top_profiles(counts: pd.DataFrame, *, pattern_len: int, tag: str, out: Path, top: int = 8) -> None:
    sub = counts[(counts.pattern_len == pattern_len) & (counts.tag == tag) & (counts.freq_rank < top)]
    if sub.empty:
        return
    models = sort_models(sub[["model", "kappa1", "kappa2", "K", "label"]].drop_duplicates())
    order = models["model"].tolist()
    label_map = dict(zip(models["model"], models["label"]))
    ncols = 7
    nrows = int(np.ceil(len(order) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 2.2 * nrows), sharex=True, sharey=True)
    axes = np.atleast_1d(axes).ravel()
    for i, m in enumerate(order):
        ax = axes[i]
        s = sub[sub.model == m].sort_values("freq_rank")
        x = s["freq_rank"].values
        med = s["mean_span_frames"].values
        ax.plot(x, med, "o-", color=K2_COLORS[models.loc[models.model == m, "kappa2"].iloc[0]], ms=3, lw=1)
        ax.set_title(label_map[m].replace("  ", "\n"), fontsize=6.5, pad=2)
        ax.set_xticks(range(top))
        if i >= len(order) - ncols:
            ax.set_xlabel("freq rank", fontsize=7)
        if i % ncols == 0:
            ax.set_ylabel("span fr", fontsize=7)
    for j in range(len(order), len(axes)):
        axes[j].axis("off")
    fig.suptitle(f"Top-{top} n-gram mean span profiles · n={pattern_len} · {tag}", y=1.01)
    fig.tight_layout()
    _save(fig, out, f"fig6_top{top}_span_profiles_n{pattern_len}_{tag}")


def sample_span_durations(
    ensemble_root: Path,
    models: list[str],
    *,
    tag: str,
    pattern_lens: list[int],
    sample_recs: int,
    max_spans_per_n: int = 150_000,
    absorb_short_bouts=None,
    rle_fn=None,
) -> dict[tuple[str, int], np.ndarray]:
    """Return {(model, n): span_frames subsample}."""
    min_bout = 3 if tag == "clean" else None
    out: dict[tuple[str, int], np.ndarray] = {}
    rng = np.random.default_rng(0)
    for mi, model in enumerate(models, 1):
        path = ensemble_root / model / "results.h5"
        if not path.exists():
            continue
        print(f"span sample [{mi}/{len(models)}] {tag} {model}", flush=True)
        buckets: dict[int, list[np.ndarray]] = {n: [] for n in pattern_lens}
        with h5py.File(path, "r") as f:
            keys = list(f.keys())
            sample = list(rng.choice(keys, size=min(sample_recs, len(keys)), replace=False))
            for key in sample:
                z = absorb_short_bouts(f[key]["syllable"][()], min_bout)
                _labs, durs, _starts = rle_fn(z)
                if durs.size == 0:
                    continue
                c = np.cumsum(durs)
                for n in pattern_lens:
                    if durs.size < n:
                        continue
                    spans = c[n - 1 :] - np.concatenate(([0], c[: -n]))
                    buckets[n].append(spans.astype(np.int64))
        for n, parts in buckets.items():
            if not parts:
                continue
            arr = np.concatenate(parts)
            if arr.size > max_spans_per_n:
                arr = rng.choice(arr, size=max_spans_per_n, replace=False)
            out[(model, n)] = arr
    return out


def fig_span_boxplots(
    spans: dict[tuple[str, int], np.ndarray],
    model_meta: pd.DataFrame,
    *,
    pattern_len: int,
    tag: str,
    out: Path,
) -> None:
    models = sort_models(model_meta)
    order = [m for m in models["model"] if (m, pattern_len) in spans]
    if not order:
        return
    label_map = dict(zip(models["model"], models["label"]))
    k2_map = dict(zip(models["model"], models["kappa2"]))
    y = np.arange(len(order))
    data = [spans[(m, pattern_len)] for m in order]
    fig, ax = plt.subplots(figsize=(8.8, 7.4))
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
        bp["boxes"][i].set_facecolor(K2_COLORS[k2_map[m]])
    ax.set_yticks(y)
    ax.set_yticklabels([label_map[m] for m in order])
    ax.set_xlabel("N-gram span duration (frames)")
    ax.set_ylabel("Model")
    ax.set_title(f"Pooled n-gram span duration · n={pattern_len} · {tag}")
    ax.set_xscale("log")
    ax.legend(
        handles=[
            Patch(facecolor=c, edgecolor="#444", label=f"k2={k}") for k, c in K2_COLORS.items()
        ],
        title="stage2_kappa",
        loc="lower right",
        frameon=False,
    )
    fig.text(
        0.01,
        0.005,
        "Source: results.h5 RLE spans · sampled recordings · outliers hidden · log x · frames",
        fontsize=7,
        color="#555",
    )
    _save(fig, out, f"fig2_span_duration_boxplot_n{pattern_len}_{tag}")


def fig_span_ecdf(
    spans: dict[tuple[str, int], np.ndarray],
    model_meta: pd.DataFrame,
    *,
    pattern_len: int,
    tag: str,
    out: Path,
) -> None:
    models = sort_models(model_meta)
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.6), sharey=True)
    for ax, K in zip(axes, [50, 75, 100]):
        sub = models[models.K == K]
        for _, row in sub.iterrows():
            key = (row["model"], pattern_len)
            if key not in spans:
                continue
            d = np.sort(spans[key])
            y = np.linspace(0, 1, d.size, endpoint=False)
            ax.plot(d, y, color=K2_COLORS[row["kappa2"]], alpha=0.85, lw=1.2)
        ax.set_xscale("log")
        ax.set_xlabel("Span duration (frames)")
        ax.set_title(f"K={K}")
        ax.set_xlim(5, 800)
    axes[0].set_ylabel("ECDF")
    axes[-1].legend(
        handles=[
            Patch(facecolor=c, edgecolor="#444", label=f"k2={k}") for k, c in K2_COLORS.items()
        ],
        frameon=False,
        fontsize=8,
        loc="lower right",
    )
    fig.suptitle(f"N-gram span ECDFs · n={pattern_len} · {tag}", y=1.02)
    fig.text(0.01, -0.02, "Source: results.h5 sampled spans · frames", fontsize=7, color="#555")
    fig.tight_layout()
    _save(fig, out, f"fig3_span_duration_ecdf_n{pattern_len}_{tag}")


def main(argv: list[str] | None = None) -> int:
    import sys

    scratch = Path(__file__).resolve().parents[1]
    if str(scratch) not in sys.path:
        sys.path.insert(0, str(scratch))

    from nor_object_mi.syllable_cleanup import maybe_absorb_short_bouts, rle_labels

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--ensemble-root",
        type=Path,
        default=Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"),
    )
    ap.add_argument("--mine-root", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--pattern-lens", nargs="+", type=int, default=[2, 3, 4, 5])
    ap.add_argument("--tags", nargs="+", default=["raw", "clean"])
    ap.add_argument("--span-sample-ns", nargs="+", type=int, default=[2, 3])
    ap.add_argument("--sample-recs", type=int, default=200)
    ap.add_argument("--skip-span-resample", action="store_true")
    args = ap.parse_args(argv)

    mine_root = args.mine_root or (args.ensemble_root / "_ngram_mine")
    out = args.out_dir or (args.ensemble_root / "_ngram_descriptives")
    out.mkdir(parents=True, exist_ok=True)

    print(f"loading counts from {mine_root}", flush=True)
    counts, summary = load_counts(mine_root)
    if counts.empty:
        print(json.dumps({"status": "failed", "reason": "no ngram_counts"}))
        return 1
    counts.to_csv(out / "ngram_counts_long.csv", index=False)
    summary.to_csv(out / "ngram_model_summary.csv", index=False)

    raw2 = counts[(counts.tag == "raw") & (counts.pattern_len == 2)]
    shared_vmax = float(np.percentile(raw2["mean_span_frames"], 95)) if len(raw2) else 80.0
    shared_vmax = max(20.0, round(shared_vmax))

    for tag in args.tags:
        for n in args.pattern_lens:
            fig_stacked_counts(counts, pattern_len=n, tag=tag, out=out)
            # Cap columns so PNG width stays under matplotlib's 2^16 px limit
            # (n≥3 inventories are huge; n=2 usually fits unclipped).
            rank_cap = {2: 120, 3: 80, 4: 60, 5: 60}.get(n, 60)
            fig_heatmap_by_K(
                counts,
                pattern_len=n,
                tag=tag,
                out=out,
                vmax=shared_vmax,
                max_ranks=rank_cap,
            )
            fig_inventory_scatter(summary, pattern_len=n, tag=tag, out=out)
            fig_top_profiles(counts, pattern_len=n, tag=tag, out=out, top=8)

    if not args.skip_span_resample:
        model_meta = (
            summary[["model", "kappa1", "kappa2", "K", "label"]]
            .drop_duplicates()
            .reset_index(drop=True)
        )
        model_names = sort_models(model_meta)["model"].tolist()
        for tag in args.tags:
            spans = sample_span_durations(
                args.ensemble_root,
                model_names,
                tag=tag,
                pattern_lens=list(args.span_sample_ns),
                sample_recs=int(args.sample_recs),
                absorb_short_bouts=maybe_absorb_short_bouts,
                rle_fn=rle_labels,
            )
            np.savez_compressed(
                out / f"span_subsamples_{tag}.npz",
                **{f"{m}__n{n}": v for (m, n), v in spans.items()},
            )
            for n in args.span_sample_ns:
                fig_span_boxplots(spans, model_meta, pattern_len=n, tag=tag, out=out)
                fig_span_ecdf(spans, model_meta, pattern_len=n, tag=tag, out=out)

    meta = {
        "mine_root": str(mine_root),
        "out_dir": str(out),
        "pattern_lens": list(args.pattern_lens),
        "tags": list(args.tags),
        "span_sample_ns": list(args.span_sample_ns),
        "heatmap_vmax": shared_vmax,
        "n_count_rows": int(len(counts)),
    }
    (out / "descriptives_summary.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", **meta}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
