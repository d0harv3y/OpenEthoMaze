"""Figures: syllable-bout ∩ movement/immobile association (interval join).

Not Pearson n_move vs n_syll. Reads CSVs from the overlap runner.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_syll_ambulation_overlap.py --dest slides
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    INK,
    PHASE_SHORT,
    PHASES,
    SEX_MARKER,
    SEX_ORDER,
    TX_COLOR,
    TX_ORDER,
    apply_style,
    fig_footnote,
    p_text,
    save_pdf_svg,
    type_scale,
)

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syll_ambulation_overlap"
)

FOOT_ID = (
    "Grain: animal × phase × novel_obj (locked ss-50). X = session frame P(movement). "
    "Y = unweighted mean over syllable bouts of P(move|bout). The diagonal is the "
    "frame-weighted identity; leaving it means bout-duration mix differs from occupancy. "
    "Pearson from syll_locomotor_association.csv. Color=tx, shape=sex. Uncorrected. "
    "Not n_move vs n_syll; not heading; not DA."
)
FOOT_I = (
    "I(raw_syllable_id ; {move, still}) in bits from the session occupancy table. "
    "Zero iff syllable identity is independent of locomotor state (frame-weighted). "
    "One-sample t vs 0 is a magnitude check (I ≥ 0). Color=tx, shape=sex. Uncorrected."
)
FOOT_DUR = (
    "Paired: median syllable-bout duration (s) among majority-movement bouts minus "
    "majority-immobile. Interval join on exclusive [start, end). Color=tx, shape=sex. "
    "Paired t from the association table. Uncorrected. Not a clock correlation."
)


def _begin(dest: str) -> dict[str, float]:
    apply_style(dest=dest)
    return type_scale(dest)


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


def _lookup(tests: pd.DataFrame, *, phase: str, contrast: str, sex: str = "pooled") -> pd.Series | None:
    m = (tests["contrast"] == contrast) & (tests["phase_layer"] == phase) & (tests["sex"] == sex)
    sub = tests[m]
    if len(sub) != 1:
        return None
    return sub.iloc[0]


def _legend(fig, *, dest: str) -> None:
    ts = type_scale(dest)
    ms = 8 if dest == "slides" else 6
    handles = [Line2D([0], [0], marker="o", color="none", markerfacecolor=TX_COLOR[t], markersize=ms, label=t) for t in TX_ORDER] + [
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
    fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=ts["legend"], ncol=5, bbox_to_anchor=(1.0, 1.04))


def _scatter_phases(
    sessions: pd.DataFrame,
    tests: pd.DataFrame,
    *,
    xcol: str,
    ycol: str,
    contrast: str,
    xlabel: str,
    ylabel: str,
    title: str,
    footnote: str,
    stem: Path,
    dest: str,
    identity: bool,
) -> None:
    ts = _begin(dest)
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 7.0), constrained_layout=True)
    for i, ph in enumerate(PHASES):
        ax = axes[i // 2][i % 2]
        panel = sessions[sessions["phase_layer"] == ph]
        x = panel[xcol].to_numpy(dtype=float)
        y = panel[ycol].to_numpy(dtype=float)
        tx = panel["tx"].to_numpy()
        sex = panel["sex"].to_numpy()
        ok = np.isfinite(x) & np.isfinite(y)
        x, y, tx, sex = x[ok], y[ok], tx[ok], sex[ok]
        for t in TX_ORDER:
            for s in SEX_ORDER:
                m = (tx == t) & (sex == s)
                if not np.any(m):
                    continue
                ax.scatter(
                    x[m],
                    y[m],
                    c=TX_COLOR[t],
                    marker=SEX_MARKER[s],
                    s=ts["scatter"],
                    alpha=0.85,
                    linewidths=0.3,
                    edgecolors="white",
                    zorder=3,
                )
        if identity and x.size:
            lo = float(min(np.min(x), np.min(y)))
            hi = float(max(np.max(x), np.max(y)))
            ax.plot([lo, hi], [lo, hi], color="#bbbbbb", lw=0.8, zorder=1)
        rec = _lookup(tests, phase=ph, contrast=contrast)
        if rec is not None:
            ax.text(
                0.04,
                0.96,
                f"r={float(rec['stat']):.2f}\n{p_text(float(rec['p']))}",
                transform=ax.transAxes,
                va="top",
                ha="left",
                fontsize=ts["cell"],
                color=INK,
            )
        ax.set_title(PHASE_SHORT[ph], fontsize=ts["annotation"])
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
    fig.suptitle(title, fontsize=ts["suptitle"])
    _legend(fig, dest=dest)
    fig_footnote(fig, footnote)
    save_pdf_svg(fig, stem)


def _strip_phases(
    sessions: pd.DataFrame,
    tests: pd.DataFrame,
    *,
    ycol: str,
    contrast: str,
    ylabel: str,
    title: str,
    footnote: str,
    stem: Path,
    dest: str,
    hline: float | None,
) -> None:
    ts = _begin(dest)
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 7.0), constrained_layout=True)
    rng = np.random.default_rng(0)
    for i, ph in enumerate(PHASES):
        ax = axes[i // 2][i % 2]
        panel = sessions[sessions["phase_layer"] == ph]
        y = panel[ycol].to_numpy(dtype=float)
        tx = panel["tx"].to_numpy()
        sex = panel["sex"].to_numpy()
        ok = np.isfinite(y)
        y, tx, sex = y[ok], tx[ok], sex[ok]
        x0 = {t: j for j, t in enumerate(TX_ORDER)}
        for t in TX_ORDER:
            for s in SEX_ORDER:
                m = (tx == t) & (sex == s)
                if not np.any(m):
                    continue
                jitter = rng.normal(0.0, 0.06, size=int(m.sum()))
                ax.scatter(
                    np.full(int(m.sum()), x0[t], dtype=float) + jitter,
                    y[m],
                    c=TX_COLOR[t],
                    marker=SEX_MARKER[s],
                    s=ts["scatter"],
                    alpha=0.85,
                    linewidths=0.3,
                    edgecolors="white",
                    zorder=3,
                )
        if hline is not None:
            ax.axhline(hline, color="#bbbbbb", lw=0.8, zorder=1)
        rec = _lookup(tests, phase=ph, contrast=contrast)
        if rec is not None:
            ax.text(
                0.04,
                0.96,
                f"Δ̄={float(rec['mean_delta']):.3g}\n{p_text(float(rec['p']))}",
                transform=ax.transAxes,
                va="top",
                ha="left",
                fontsize=ts["cell"],
                color=INK,
            )
        ax.set_xticks(list(range(len(TX_ORDER))))
        ax.set_xticklabels(list(TX_ORDER))
        ax.set_title(PHASE_SHORT[ph], fontsize=ts["annotation"])
        ax.set_ylabel(ylabel)
    fig.suptitle(title, fontsize=ts["suptitle"])
    _legend(fig, dest=dest)
    fig_footnote(fig, footnote)
    save_pdf_svg(fig, stem)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)
    out = args.run_dir
    dest = args.dest
    sessions = pd.read_csv(out / "syll_locomotor_session.csv")
    tests = pd.read_csv(out / "syll_locomotor_association.csv")
    if "hit_p05" in tests.columns:
        tests["hit_p05"] = _as_bool(tests["hit_p05"])

    _scatter_phases(
        sessions,
        tests,
        xcol="p_session_move",
        ycol="mean_bout_move_frac",
        contrast="session_p_move_vs_unweighted_bout_frac",
        xlabel="session P(move)",
        ylabel="unweighted mean P(move|bout)",
        title="Syllable bouts vs locomotor occupancy (not two clocks)",
        footnote=FOOT_ID,
        stem=out / f"fig_syll_locomotor_identity_{dest}",
        dest=dest,
        identity=True,
    )
    _strip_phases(
        sessions,
        tests,
        ycol="i_syllable_locomotor_bits",
        contrast="i_syllable_locomotor_vs_0",
        ylabel="I(syllable ; locomotor) / bits",
        title="Syllable identity × movement vs immobile",
        footnote=FOOT_I,
        stem=out / f"fig_syll_locomotor_mi_{dest}",
        dest=dest,
        hline=0.0,
    )
    _strip_phases(
        sessions,
        tests,
        ycol="delta_median_duration_s_move_minus_still",
        contrast="median_duration_majority_move_vs_still",
        ylabel="median duration Δ (move − still) / s",
        title="Syllable-bout duration by majority locomotor state",
        footnote=FOOT_DUR,
        stem=out / f"fig_syll_locomotor_duration_{dest}",
        dest=dest,
        hline=0.0,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
