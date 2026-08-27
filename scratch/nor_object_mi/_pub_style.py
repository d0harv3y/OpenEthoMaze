"""Lab publication style. Import from fig_*.py next to this file.

Dest: slides (PowerPoint, default) or paper (journal).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

TX_ORDER = ("noSD", "GHSD", "RBSD")
SEX_ORDER = ("F", "M")
TX_COLOR = {
    "noSD": "#1b9e77",
    "GHSD": "#d95f02",
    "RBSD": "#7570b3",
}
SEX_MARKER = {"F": "o", "M": "v"}
INK = "#1a1a1a"
MUTE = "#6b6b6b"
FIGSIZE_SINGLE = (3.5, 3.2)
FIGSIZE_DOUBLE = (7.2, 4.8)
FIGSIZE_SLIDES = (12.8, 7.2)
SAVE_DPI = 300
DESTS = ("slides", "paper")

_PAPER_TYPE = {
    "font.size": 9,
    "suptitle": 11,
    "annotation": 7.5,
    "cell": 6.5,
    "footnote": 6.5,
    "legend": 8,
    "scatter": 9,
    "violin_scatter": 12,
}
_SLIDES_TYPE = {
    "font.size": 13,
    "suptitle": 16,
    "annotation": 12,
    "cell": 11,
    "footnote": 11,
    "legend": 12,
    "scatter": 18,
    "violin_scatter": 36,
}

_BASE_RC = {
    "font.family": "DejaVu Sans",
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "text.color": INK,
    "figure.dpi": 150,
    "savefig.dpi": SAVE_DPI,
    "savefig.bbox": "tight",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
}

RCPARAMS = {**_BASE_RC, "font.size": _PAPER_TYPE["font.size"]}

_DEST = "slides"
_TYPE = _SLIDES_TYPE

PHASES = ("NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr")
PHASE_SHORT = {
    "NOR_BL": "BL",
    "NOR_TX": "TX",
    "NOR_REC3hr": "REC3",
    "NOR_REC11hr": "REC11",
}
PILOT_MODEL = "paramscan_s1-1e8_s2-1e5_ss-50"


def type_scale(dest: str | None = None) -> dict[str, float]:
    d = dest or _DEST
    if d not in DESTS:
        raise ValueError(f"dest must be one of {DESTS}, got {d!r}")
    return dict(_SLIDES_TYPE if d == "slides" else _PAPER_TYPE)


def apply_style(*, dest: str = "slides") -> None:
    """Set rcParams for dest. Default is slides (PowerPoint)."""
    global _DEST, _TYPE
    _TYPE = type_scale(dest)
    _DEST = dest
    plt.rcParams.update({**_BASE_RC, "font.size": _TYPE["font.size"]})


def text_on_cmap(
    v: float,
    *,
    cmap: str = "viridis",
    vmin: float = 0.0,
    vmax: float = 1.0,
) -> str:
    """White vs ink from the *mapped color's* luma, not from the data value."""
    if v != v:  # NaN
        return INK
    span = vmax - vmin
    t = 0.5 if span == 0 else (v - vmin) / span
    t = min(1.0, max(0.0, t))
    r, g, b, _a = plt.get_cmap(cmap)(t)
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "white" if luma < 0.5 else INK


def p_text(p: float) -> str:
    if p != p:  # NaN
        return "p = n/a"
    if p < 1e-4:
        return "p < 10⁻⁴"
    if p < 0.001:
        return f"p = {p:.1e}"
    return f"p = {p:.3f}"


def fig_footnote(
    fig: plt.Figure,
    text: str,
    *,
    fontsize: float | None = None,
    color: str = MUTE,
    y: float = -0.06,
) -> None:
    """Word-wrap a footnote to a readable paragraph inside the figure width.

    Place it clear of the legend. A legend sitting on this text is not done.
    Prefer `fig_legend_and_footnote` when the figure has a legend.
    """
    pt = float(_TYPE["footnote"] if fontsize is None else fontsize)
    char_pt = 0.62 * pt
    nchars = max(40, int((fig.get_figwidth() * 72 * 0.90) / char_pt))
    wrapped = textwrap.fill(" ".join(text.split()), width=nchars)
    fig.text(0.0, y, wrapped, fontsize=pt, color=color, ha="left", va="top")


def tx_sex_legend_handles(*, dest: str = "slides") -> list:
    """Color = tx, shape = sex. Caller places them with `fig_legend_and_footnote`."""
    ms = 8 if dest == "slides" else 6
    return [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=TX_COLOR[t], markersize=ms, label=t)
        for t in TX_ORDER
    ] + [
        Line2D(
            [0],
            [0],
            marker=SEX_MARKER[s],
            color="none",
            markerfacecolor=INK,
            markersize=ms,
            label=s,
        )
        for s in SEX_ORDER
    ]


def fig_legend_and_footnote(
    fig: plt.Figure,
    handles: list,
    text: str,
    *,
    dest: str = "slides",
) -> None:
    """Legend in a reserved footer, footnote under it. Same y-band is not done."""
    ts = type_scale(dest)
    pt = float(ts["footnote"])
    char_pt = 0.62 * pt
    nchars = max(40, int((fig.get_figwidth() * 72 * 0.90) / char_pt))
    wrapped = textwrap.fill(" ".join(text.split()), width=nchars)
    if dest != "slides":
        fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=ts["legend"], ncol=5)
        fig_footnote(fig, text)
        return
    engine = fig.get_layout_engine()
    if engine is not None:
        engine.set(h_pad=0.04, w_pad=0.04, rect=(0.0, 0.18, 1.0, 0.78))
    fig.legend(
        handles=handles,
        loc="center",
        bbox_to_anchor=(0.5, 0.11),
        bbox_transform=fig.transFigure,
        frameon=False,
        fontsize=ts["legend"],
        ncol=5,
    )
    fig.text(0.0, 0.02, wrapped, fontsize=pt, color=MUTE, ha="left", va="bottom")


def panel_stats_box(ax, lines: list[str], *, dest: str = "slides") -> None:
    """Inset labeled stats. Letter codes that only the footnote can decode are not done."""
    ts = type_scale(dest)
    ax.text(
        0.04,
        0.96,
        "\n".join(lines),
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=ts["cell"],
        color=INK,
        linespacing=1.25,
        zorder=5,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#dddddd", lw=0.6),
    )


def save_pdf_svg(fig, stem: Path, *, dpi: int = SAVE_DPI) -> None:
    """PDF for print/archive; SVG for PowerPoint (text stays text)."""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight", dpi=dpi)
    fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {stem.with_suffix('.pdf')}")
    print(f"wrote {stem.with_suffix('.svg')}")


def save_png(fig, stem: Path, *, dpi: int = SAVE_DPI, close: bool = True) -> None:
    """Raster PNG for PowerPoint when SVG→shapes conversion fails."""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".png"), bbox_inches="tight", dpi=dpi)
    if close:
        plt.close(fig)
    print(f"wrote {stem.with_suffix('.png')}")


def save_pdf_png(fig, stem: Path, *, dpi: int = SAVE_DPI) -> None:
    """Old name. Writes PDF+SVG, not PNG."""
    save_pdf_svg(fig, stem, dpi=dpi)
