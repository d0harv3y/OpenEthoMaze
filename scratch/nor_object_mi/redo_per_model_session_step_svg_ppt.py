"""Redo 4 per-animal session-step per-model Kruskal SVGs for PowerPoint.

Matplotlib vector SVGs (imshow / path fonts / clipPaths) often draw blank in
PowerPoint. This script:

1. Redraws heatmaps with rectangle cells (no imshow bitmap).
2. Writes PDF + high-DPI PNG.
3. Overwrites ``.svg`` as a PNG-embedded wrapper (PPT-safe).

Also writes ``*_linked.svg`` (external ``xlink:href`` to the PNG).

    uv run python scratch/nor_object_mi/redo_per_model_session_step_svg_ppt.py
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle
from PIL import Image

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    INK,
    MUTE,
    SEX_ORDER,
    apply_style,
    text_on_cmap,
    type_scale,
)
from nor_object_mi.cluster13_frame_share import short_model_label  # noqa: E402
from nor_object_mi.fig_prox_quad_comp_violins import ROLE_LAB, ROLES  # noqa: E402
from nor_object_mi.fig_slides_pack import (  # noqa: E402
    NLP_VMAX,
    SEX_LAB,
    _model_x_mats,
    _neglog10_p,
)
from nor_object_mi.simpler_first_session_paired import (  # noqa: E402
    PHASE_STEP_NAMES,
    STEP_LAB,
)

ROOT = Path(
    r"D:\sack\datas\impress\nor_per_animal_paramscan"
    r"\_nor_object_mi\simpler_first_prox_quad_per_animal_session_step_figs"
)
FIGURES = ROOT / "figures"

BOARDS: tuple[tuple[str, str, str], ...] = (
    ("quad", "shannon", "Shannon (bits) · quadrant"),
    ("quad", "richness", "richness · quadrant"),
    ("prox", "shannon", "Shannon (bits) · 0.10 m prox"),
    ("prox", "richness", "richness · 0.10 m prox"),
)


def _p_cell_text_ascii(p: float) -> str:
    """ASCII-only cell text — PPT SVG often drops unicode superscripts."""
    if not np.isfinite(p):
        return ""
    if p < 1e-4:
        return "<1e-4"
    if p < 0.001:
        return f"{p:.1e}"
    return f"{p:.3f}"


def _draw_rect_heatmap(
    ax,
    pmat: np.ndarray,
    hits: np.ndarray,
    *,
    y_labels: list[str],
    x_labels: list[str],
    title: str,
    ts: dict,
    show_ylabel: bool,
    cmap,
    norm: Normalize,
) -> None:
    n_r, n_c = pmat.shape
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    for i in range(n_r):
        for j in range(n_c):
            v = nlp[i, j]
            if not np.isfinite(v):
                facecolor = "#dddddd"
                tcolor = INK
            else:
                facecolor = cmap(norm(v))
                tcolor = text_on_cmap(float(v), vmin=0.0, vmax=NLP_VMAX)
            ax.add_patch(
                Rectangle(
                    (j - 0.5, i - 0.5),
                    1.0,
                    1.0,
                    facecolor=facecolor,
                    edgecolor="white",
                    linewidth=0.4,
                    antialiased=False,
                )
            )
            p = pmat[i, j]
            if np.isfinite(p) and np.isfinite(v):
                mark = "*" if hits[i, j] else ""
                ax.text(
                    j,
                    i,
                    mark + _p_cell_text_ascii(p),
                    ha="center",
                    va="center",
                    fontsize=ts["cell"] * 0.7,
                    color=tcolor,
                    clip_on=False,
                )
    ax.set_xlim(-0.5, n_c - 0.5)
    ax.set_ylim(n_r - 0.5, -0.5)
    ax.set_xticks(range(n_c))
    ax.set_xticklabels(x_labels, fontsize=ts["annotation"], rotation=35, ha="right")
    ax.set_yticks(range(n_r))
    if show_ylabel:
        ax.set_yticklabels(y_labels, fontsize=ts["cell"] * 0.8)
        ax.set_ylabel("model", fontsize=ts["annotation"])
    else:
        ax.set_yticklabels([])
    ax.set_title(title, loc="left", fontweight="bold", color=INK)
    ax.set_aspect("auto")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color(INK)
        spine.set_linewidth(0.6)


def redraw_one(roi: str, kind: str, title_bit: str) -> Path:
    apply_style(dest="slides")
    ts = type_scale("slides")
    kr = pd.read_csv(ROOT / f"kruskal_per_model_{roi}_{kind}_session_step.csv")
    labels = pd.read_csv(ROOT / f"model_labels_{roi}_{kind}_session_step.csv")
    lab_map = dict(zip(labels["model"].astype(str), labels["label"].astype(str)))
    models = sorted(str(x) for x in kr["model"].unique())
    y_labels = [lab_map.get(m, short_model_label(m)) for m in models]
    x_labels = [STEP_LAB[s] for s in PHASE_STEP_NAMES]

    cmap = plt.get_cmap("viridis")
    norm = Normalize(vmin=0.0, vmax=NLP_VMAX)

    n_row = len(ROLES)
    fig_w, fig_h = 12.0, 3.2 * n_row + 0.8
    fig, axes = plt.subplots(n_row, len(SEX_ORDER), figsize=(fig_w, fig_h), squeeze=False)
    fig.subplots_adjust(left=0.12, right=0.88, top=0.90, bottom=0.10, hspace=0.38, wspace=0.18)

    for i, role in enumerate(ROLES):
        for j, sex in enumerate(SEX_ORDER):
            ax = axes[i, j]
            pmat, hits = _model_x_mats(
                kr,
                models=models,
                x_values=list(PHASE_STEP_NAMES),
                x_col="session_step",
                row_value=role,
                row_col="role",
                sex=sex,
            )
            _draw_rect_heatmap(
                ax,
                pmat,
                hits,
                y_labels=y_labels,
                x_labels=x_labels,
                title=f"Δ{ROLE_LAB[role]} · {SEX_LAB.get(sex, sex)}",
                ts=ts,
                show_ylabel=(j == 0),
                cmap=cmap,
                norm=norm,
            )

    # Manual colorbar as rects — matplotlib colorbar embeds a bitmap <image>
    # that PowerPoint often drops entirely.
    cax = fig.add_axes([0.90, 0.18, 0.018, 0.64])
    n_bar = 64
    for k in range(n_bar):
        v0 = k / n_bar * NLP_VMAX
        cax.add_patch(
            Rectangle(
                (0.0, k / n_bar),
                1.0,
                1.0 / n_bar,
                facecolor=cmap(norm(v0)),
                edgecolor="none",
                antialiased=False,
                transform=cax.transAxes,
                clip_on=False,
            )
        )
    cax.set_xlim(0, 1)
    cax.set_ylim(0, 1)
    cax.set_xticks([])
    cax.yaxis.tick_right()
    cax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
    cax.set_yticklabels(
        [f"{v:.1f}" for v in (0.0, 1.0, 2.0, 3.0, 4.0)],
        fontsize=ts["cell"],
    )
    cax.set_ylabel("-log10(p)", fontsize=ts["annotation"], color=INK)
    cax.yaxis.set_label_position("right")
    for spine in cax.spines.values():
        spine.set_color(INK)
        spine.set_linewidth(0.6)

    fig.suptitle(
        f"Per-model Kruskal on Δ ~ condition ({title_bit})",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=0.98,
    )
    fig.text(
        0.5,
        0.02,
        (
            "Per-model Kruskal on paired Δ ~ condition within sex. "
            "y = paramscan fit cell (s1/s2/ss). "
            "Panel grid: rows = Δfam|Δnvl|ΔDR, cols = sex. "
            "Heatmap x = session_step. Color = -log10(p), clip 4; "
            "* = BH q < 0.05 within model × role (session_step × sex). "
            "PPT-safe SVG (rect cells, path fonts)."
        ),
        ha="center",
        va="bottom",
        fontsize=ts["footnote"],
        color=MUTE,
    )

    stem = FIGURES / f"fig_per_model_{roi}_{kind}_session_step_kruskal_heatmap"
    with mpl.rc_context({"pdf.fonttype": 42}):
        fig.savefig(stem.with_suffix(".pdf"), format="pdf", bbox_inches="tight")
        fig.savefig(stem.with_suffix(".png"), format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    _write_ppt_svg_from_png(stem.with_suffix(".png"), stem.with_suffix(".svg"))
    print(f"rewrote {stem.name}.{{svg,pdf,png}}", flush=True)
    return stem.with_suffix(".svg")


def _write_ppt_svg_from_png(png: Path, svg: Path) -> None:
    """Wrap a PNG as SVG — PowerPoint renders this; matplotlib vector SVG often does not."""
    im = Image.open(png)
    w, h = im.size
    b64 = base64.b64encode(png.read_bytes()).decode("ascii")
    svg.write_text(
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            f"  <title>{svg.stem}</title>\n"
            f'  <image width="{w}" height="{h}" '
            f'xlink:href="data:image/png;base64,{b64}"/>\n'
            "</svg>\n"
        ),
        encoding="utf-8",
    )
    linked = svg.with_name(svg.stem + "_linked.svg")
    linked.write_text(
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            f'  <image width="{w}" height="{h}" xlink:href="{png.name}"/>\n'
            "</svg>\n"
        ),
        encoding="utf-8",
    )


def main() -> int:
    FIGURES.mkdir(parents=True, exist_ok=True)
    paths = [redraw_one(roi, kind, title) for roi, kind, title in BOARDS]
    for p in paths:
        print(f"  {p.name}: bytes={p.stat().st_size}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
