"""Publication figures: INFO object-prox DR vs pause syllable Y.

Reads CSVs from a ``simpler_first_info_dr_pause`` run folder (see INFO_info_dr_pause.md).

Regen (OpenEthoMaze repo root):

    uv run python scratch/nor_object_mi/fig_simpler_first_info_dr_pause.py --y-metric presence_novel
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_SLIDES,
    INK,
    MUTE,
    PHASE_SHORT,
    PHASES,
    SEX_ORDER,
    TX_COLOR,
    TX_ORDER,
    apply_style,
    fig_footnote,
    fig_legend_and_footnote,
    panel_stats_box,
    save_pdf_png,
    text_on_cmap,
    tx_sex_legend_handles,
    type_scale,
)
from nor_object_mi.info_dr_pause_delta import (  # noqa: E402
    DR_COL,
    DEFAULT_Y_METRIC,
    YMetricSpec,
    default_out_dir,
    get_y_metric_spec,
    y_metric_choices,
)

ROOT = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
MI_VMAX = 0.12
NLP_VMAX = 4.0


def _read_spec(run_dir: Path, y_metric: str | None) -> YMetricSpec:
    summary_path = run_dir / "run_summary.json"
    token = y_metric
    if token is None and summary_path.exists():
        token = str(json.loads(summary_path.read_text(encoding="utf-8")).get("y_metric", DEFAULT_Y_METRIC))
    token = token or DEFAULT_Y_METRIC
    return get_y_metric_spec(token)


def _foot_scatter(spec: YMetricSpec, *, dest: str) -> str:
    y_desc = (
        f"binary pause presence on novel_obj (median p_k > 0 across models)"
        if spec.binary
        else getattr(
            spec,
            "y_desc",
            f"{spec.label} (median across 21 kpMS models)",
        )
    )
    long = (
        "Grain: animal × phase × novel_obj. Each point is one animal: object-prox "
        f"exclusive DR vs cluster-13 {y_desc}. Color = tx; rows = sex (F / M). "
        "Stats inset: Miller–Madow MI (mi_mm_bits), permutation p on Y shuffle within cell, "
        "Spearman ρ. Between-animal INFO — not within-bout stim↔syll MI. BH family = "
        "8 cells (4 phases × 2 sexes). Not DA; not DR vs 0."
    )
    short = f"Object-prox DR vs {spec.label}, by sex × phase."
    return short if dest == "slides" else long


def _foot_heat(spec: YMetricSpec, *, dest: str) -> str:
    long = (
        "Grain: animal × phase × novel_obj; sex-stratified INFO cells. "
        f"Y = {spec.label}. Left: I(DR; Y) in bits (mi_mm_bits). "
        "Right: Spearman ρ. * = BH q < 0.05 on permutation p (8-cell family). "
        "Third panel: −log₁₀(perm p). Not DA."
    )
    short = f"MI / Spearman / perm p summary for {spec.token}."
    return short if dest == "slides" else long


def _begin(dest: str) -> dict[str, float]:
    apply_style(dest=dest)
    return type_scale(dest)


def _p_compact(p: float) -> str:
    if not np.isfinite(p):
        return "n/a"
    if p < 1e-4:
        return "<10⁻⁴"
    if p < 0.001:
        return f"{p:.1e}"
    return f"{p:.2f}"


def _as_bool(s: object) -> bool:
    if isinstance(s, (bool, np.bool_)):
        return bool(s)
    return str(s).lower() in ("true", "1")


def _cell_tests(tests: pd.DataFrame, *, phase: str, sex: str) -> pd.Series | None:
    row = tests[(tests["phase_layer"] == phase) & (tests["sex"] == sex)]
    if len(row) != 1:
        return None
    return row.iloc[0]


def _scatter_panel(
    ax,
    panel: pd.DataFrame,
    rec: pd.Series | None,
    *,
    spec: YMetricSpec,
    rng: np.random.Generator,
    ts: dict[str, float],
    show_ylabel: bool,
    title: str,
) -> None:
    x = panel[DR_COL].to_numpy(dtype=np.float64)
    y = panel[spec.y_col].to_numpy(dtype=np.float64)
    tx = panel["tx"].to_numpy()
    ok = np.isfinite(x) & np.isfinite(y)
    x, y, tx = x[ok], y[ok], tx[ok]
    jitter_x = rng.normal(0.0, 0.012, size=x.size)
    jitter_y = rng.normal(0.0, 0.06 if spec.binary else 0.004, size=y.size)
    for t in TX_ORDER:
        m = tx == t
        if not np.any(m):
            continue
        ax.scatter(
            x[m] + jitter_x[m],
            y[m] + jitter_y[m],
            s=ts["scatter"],
            c=TX_COLOR[t],
            alpha=0.78,
            edgecolors="none",
            zorder=3,
        )
    ax.axhline(0.0, color="#cccccc", lw=0.7, ls="--", zorder=0)
    ax.axvline(0.0, color="#cccccc", lw=0.7, ls="--", zorder=0)
    if x.size:
        pad_x = max(0.08, 0.05 * (float(np.nanmax(x)) - float(np.nanmin(x)) + 1e-9))
        ax.set_xlim(float(np.nanmin(x)) - pad_x, float(np.nanmax(x)) + pad_x)
    if spec.binary:
        ax.set_ylim(-0.18, 1.18)
        ax.set_yticks([0.0, 1.0])
        ax.set_yticklabels(["absent", "present"])
    elif y.size:
        pad_y = max(0.02, 0.08 * (float(np.nanmax(y)) - float(np.nanmin(y)) + 1e-9))
        ax.set_ylim(float(np.nanmin(y)) - pad_y, float(np.nanmax(y)) + pad_y)
    ax.set_title(title, loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    if show_ylabel:
        ax.set_ylabel(spec.y_axis)
    ax.set_xlabel("object-prox DR (exclusive)")
    if rec is not None:
        median_y = float(rec.get("median_y", rec.get("median_delta_p", float("nan"))))
        frac_pos = float(rec.get("frac_y_positive", float("nan")))
        rho = float(rec["spearman_rho"])
        rho_s = f"{rho:.2f}" if np.isfinite(rho) else "n/a"
        lines = [
            f"n={int(rec['n_finite'])}",
            f"MI_mm = {float(rec['mi_mm_bits']):.3f} bit",
            f"perm {_p_compact(float(rec['perm_p']))}",
            f"ρ = {rho_s}  {_p_compact(float(rec['spearman_p']))}",
        ]
        if spec.binary and np.isfinite(frac_pos):
            lines.insert(1, f"P(present) = {frac_pos:.2f}")
        else:
            lines.insert(1, f"median Y = {median_y:.3f}")
        if rec is not None and _as_bool(rec.get("y_degenerate", False)):
            lines.append("H(Y)=0; INFO vacuous")
        panel_stats_box(ax, lines, dest="slides")


def fig_scatter(
    joined: pd.DataFrame,
    tests: pd.DataFrame,
    out: Path,
    *,
    spec: YMetricSpec,
    dest: str = "slides",
) -> None:
    ts = _begin(dest)
    rng = np.random.default_rng(0)
    if dest == "slides":
        fig, axes = plt.subplots(2, 4, figsize=FIGSIZE_SLIDES, layout="constrained")
    else:
        fig, axes = plt.subplots(2, 4, figsize=(7.6, 5.6), layout="constrained")
    for r, sex in enumerate(SEX_ORDER):
        for c, ph in enumerate(PHASES):
            ax = axes[r, c]
            panel = joined[(joined["phase_layer"] == ph) & (joined["sex"] == sex)]
            rec = _cell_tests(tests, phase=ph, sex=sex)
            _scatter_panel(
                ax,
                panel,
                rec,
                spec=spec,
                rng=rng,
                ts=ts,
                show_ylabel=(c == 0),
                title=f"{PHASE_SHORT[ph]} · {sex}",
            )
    fig.suptitle(
        f"INFO: object-prox DR vs {spec.label}",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_legend_and_footnote(
        fig,
        [h for h in tx_sex_legend_handles(dest=dest) if h.get_label() in TX_ORDER],
        _foot_scatter(spec, dest=dest),
        dest=dest,
    )
    stem = f"fig_info_dr_pause_scatter__{spec.token}"
    save_pdf_png(fig, out / stem)


def _metric_mat(tests: pd.DataFrame, col: str) -> np.ndarray:
    mat = np.full((len(PHASES), len(SEX_ORDER)), np.nan)
    for i, ph in enumerate(PHASES):
        for j, sex in enumerate(SEX_ORDER):
            rec = _cell_tests(tests, phase=ph, sex=sex)
            if rec is not None and col in rec.index:
                mat[i, j] = float(rec[col])
    return mat


def _hit_mat(tests: pd.DataFrame) -> np.ndarray:
    mat = np.zeros((len(PHASES), len(SEX_ORDER)), dtype=bool)
    for i, ph in enumerate(PHASES):
        for j, sex in enumerate(SEX_ORDER):
            rec = _cell_tests(tests, phase=ph, sex=sex)
            if rec is not None and "hit_fdr05" in rec.index:
                mat[i, j] = _as_bool(rec["hit_fdr05"])
    return mat


def _draw_phase_sex_heatmap(
    ax,
    mat: np.ndarray,
    hits: np.ndarray,
    *,
    title: str,
    cmap: str,
    vmin: float,
    vmax: float,
    fmt: str,
    ts: dict[str, float],
) -> object:
    im = ax.imshow(mat, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(SEX_ORDER)))
    ax.set_xticklabels(SEX_ORDER, fontsize=ts["annotation"])
    ax.set_yticks(range(len(PHASES)))
    ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES], fontsize=ts["annotation"])
    ax.set_title(title, loc="left", fontweight="bold", color=INK)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            if not np.isfinite(v):
                continue
            mark = "*" if hits[i, j] else ""
            ax.text(
                j,
                i,
                mark + fmt.format(v),
                ha="center",
                va="center",
                fontsize=ts["cell"],
                color=text_on_cmap(v, cmap=cmap, vmin=vmin, vmax=vmax),
            )
    return im


def fig_heatmaps(tests: pd.DataFrame, out: Path, *, spec: YMetricSpec, dest: str = "slides") -> None:
    ts = _begin(dest)
    hits = _hit_mat(tests)
    mi = _metric_mat(tests, "mi_mm_bits")
    rho = _metric_mat(tests, "spearman_rho")
    perm_p = _metric_mat(tests, "perm_p")
    nlp = np.where(np.isfinite(perm_p), -np.log10(np.clip(perm_p, 1e-300, 1.0)), np.nan)

    if dest == "slides":
        fig = plt.figure(figsize=FIGSIZE_SLIDES)
        gs = fig.add_gridspec(1, 3, left=0.07, right=0.98, top=0.88, bottom=0.22, wspace=0.32)
    else:
        fig = plt.figure(figsize=(7.6, 4.2))
        gs = fig.add_gridspec(1, 3, left=0.08, right=0.98, top=0.86, bottom=0.26, wspace=0.35)

    ax_mi = fig.add_subplot(gs[0, 0])
    ax_rho = fig.add_subplot(gs[0, 1])
    ax_nlp = fig.add_subplot(gs[0, 2])

    mi_vmax = max(MI_VMAX, float(np.nanmax(mi)) if np.any(np.isfinite(mi)) else MI_VMAX)
    im_mi = _draw_phase_sex_heatmap(
        ax_mi,
        mi,
        hits,
        title="A  MI (Miller–Madow bits)",
        cmap="viridis",
        vmin=0.0,
        vmax=mi_vmax,
        fmt="{:.3f}",
        ts=ts,
    )
    im_rho = _draw_phase_sex_heatmap(
        ax_rho,
        rho,
        hits,
        title="B  Spearman ρ",
        cmap="RdBu_r",
        vmin=-1.0,
        vmax=1.0,
        fmt="{:.2f}",
        ts=ts,
    )
    im_nlp = _draw_phase_sex_heatmap(
        ax_nlp,
        nlp,
        hits,
        title="C  −log₁₀(perm p)",
        cmap="viridis",
        vmin=0.0,
        vmax=NLP_VMAX,
        fmt="{:.2f}",
        ts=ts,
    )

    cbar_y = 0.12 if dest == "slides" else 0.10
    for im, lab, ax in (
        (im_mi, "MI bits", ax_mi),
        (im_rho, "Spearman ρ", ax_rho),
        (im_nlp, "−log₁₀(perm p)", ax_nlp),
    ):
        pos = ax.get_position()
        cax = fig.add_axes([pos.x0, cbar_y, pos.width, 0.012])
        fig.colorbar(im, cax=cax, orientation="horizontal", label=lab)

    fig.suptitle(
        f"INFO summary: object-prox DR vs {spec.label}",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=0.98,
    )
    fig_footnote(fig, _foot_heat(spec, dest=dest), y=0.02, color=MUTE)
    stem = f"fig_info_dr_pause_heatmaps__{spec.token}"
    save_pdf_png(fig, out / stem)


def _figures_info_md(spec: YMetricSpec) -> str:
    return f"""## Figures

| File | Question | Inputs | Encoding |
|------|----------|--------|----------|
| `fig_info_dr_pause_scatter__{spec.token}` | DR vs {spec.label} within sex × phase? | joined + tests CSVs | scatter; color = tx |
| `fig_info_dr_pause_heatmaps__{spec.token}` | MI / ρ / perm p lattice? | tests CSV | 1×3 heatmaps |

Regen:

    uv run python scratch/nor_object_mi/fig_simpler_first_info_dr_pause.py --y-metric {spec.token}
"""


def _patch_info_md(run_dir: Path, spec: YMetricSpec) -> None:
    info_path = run_dir / "INFO_info_dr_pause.md"
    if not info_path.exists():
        return
    text = info_path.read_text(encoding="utf-8")
    block = _figures_info_md(spec)
    if "## Figures" in text:
        head = text.split("## Figures", 1)[0].rstrip()
        info_path.write_text(head + "\n\n" + block.strip() + "\n", encoding="utf-8")
    else:
        info_path.write_text(text.rstrip() + "\n\n" + block.strip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument(
        "--y-metric",
        choices=y_metric_choices(),
        default=None,
        help="select run folder suffix; inferred from run_summary.json if omitted",
    )
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    if args.run_dir is not None:
        run = args.run_dir
    elif args.y_metric is not None:
        run = default_out_dir(ROOT, args.y_metric)
    else:
        run = default_out_dir(ROOT, DEFAULT_Y_METRIC)
    spec = _read_spec(run, args.y_metric)

    out = args.out_dir or (run / "figures")
    out.mkdir(parents=True, exist_ok=True)

    joined = pd.read_csv(run / "info_dr_pause_joined_per_animal.csv")
    tests = pd.read_csv(run / "info_dr_pause_tests_long.csv")

    fig_scatter(joined, tests, out, spec=spec, dest=args.dest)
    fig_heatmaps(tests, out, spec=spec, dest=args.dest)
    _patch_info_md(run, spec)
    print(f"wrote figures under {out} ({spec.token})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
