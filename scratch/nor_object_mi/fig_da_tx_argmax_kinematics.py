"""TX pooled volcano right-wing: one syllable per model, kinematics.

Winner = argmax median_delta_p in da_syllable_tests_long (sex=all) at NOR_TX.
Ids are not portable. Compare via syllable_prototypes_clustered.csv (cluster_id).

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_da_tx_argmax_kinematics.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_DOUBLE,
    INK,
    apply_style,
    fig_legend_and_footnote,
    save_pdf_png,
)

DEFAULT_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
DEFAULT_SIG = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures"
)
STEPS = (
    ("no_obj->identical", "presence"),
    ("identical->novel", "novelty"),
)
WINNER_CSV = "tx_pooled_argmax_syllable.csv"


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


def tx_argmax_table(tests: pd.DataFrame, proto: pd.DataFrame) -> pd.DataFrame:
    t = tests[tests["phase_layer"] == "NOR_TX"].copy()
    t["median_delta_p"] = pd.to_numeric(t["median_delta_p"], errors="coerce")
    t["hit"] = _as_bool(t["hit_fdr05"])
    rows: list[dict[str, object]] = []
    for (model, step), g in t.groupby(["model", "step"], sort=True):
        if step not in {s for s, _ in STEPS}:
            continue
        g = g.sort_values("median_delta_p", ascending=False)
        a = g.iloc[0]
        d1 = float(a["median_delta_p"])
        d2 = float(g.iloc[1]["median_delta_p"]) if len(g) > 1 else float("nan")
        rows.append(
            {
                "model": str(model),
                "phase_layer": "NOR_TX",
                "step": str(step),
                "raw_syllable_id": int(a["raw_syllable_id"]),
                "median_delta_p": d1,
                "median_delta_p_second": d2,
                "gap": d1 - d2,
                "hit_fdr05": bool(a["hit"]),
                "n": int(a["n"]),
            }
        )
    w = pd.DataFrame(rows)
    keep = [
        "model",
        "ss",
        "raw_syllable_id",
        "cluster_id",
        "n_bouts",
        "syllable_sig_mean_speed_mps",
        "syllable_sig_mean_abs_dheading",
        "syllable_sig_mean_nose_tail_m",
        "syllable_mean_duration_s",
        "syllable_mean_straightness",
        "syllable_mean_net_dheading_rad",
    ]
    return w.merge(proto[keep], on=["model", "raw_syllable_id"], how="left")


def fig_argmax_kinematics(winners: pd.DataFrame, proto: pd.DataFrame, out: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    # One row per model (presence and novelty share the id)
    w = winners[winners["step"] == "identical->novel"].copy()
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    axes[0].scatter(
        proto["syllable_mean_duration_s"],
        proto["syllable_sig_mean_speed_mps"],
        s=10 if dest == "slides" else 6,
        c="#c8c8c8",
        alpha=0.35,
        edgecolors="none",
        zorder=1,
    )
    axes[0].scatter(
        w["syllable_mean_duration_s"],
        w["syllable_sig_mean_speed_mps"],
        s=48 if dest == "slides" else 28,
        c="#0072B2",
        marker="o",
        edgecolors=INK,
        linewidths=0.5,
        zorder=3,
    )
    axes[0].set_xlabel("mean bout duration (s)")
    axes[0].set_ylabel("mean speed (m/s)")
    axes[0].set_title("A  timing × speed", loc="left", fontweight="bold", color=INK)

    axes[1].scatter(
        proto["syllable_mean_straightness"],
        proto["syllable_sig_mean_abs_dheading"],
        s=10 if dest == "slides" else 6,
        c="#c8c8c8",
        alpha=0.35,
        edgecolors="none",
        zorder=1,
    )
    axes[1].scatter(
        w["syllable_mean_straightness"],
        w["syllable_sig_mean_abs_dheading"],
        s=48 if dest == "slides" else 28,
        c="#0072B2",
        marker="o",
        edgecolors=INK,
        linewidths=0.5,
        zorder=3,
    )
    axes[1].set_xlabel("straightness")
    axes[1].set_ylabel("mean |Δheading| (rad/frame)")
    axes[1].set_title("B  path × heading", loc="left", fontweight="bold", color=INK)

    n_c13 = int((w["cluster_id"] == 13).sum())
    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor="#c8c8c8",
            markersize=8,
            label="all prototypes",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor="#0072B2",
            markeredgecolor=INK,
            markersize=9,
            label=f"TX pooled argmax (n={len(w)}; cluster 13 = {n_c13}/21)",
        ),
    ]
    fig.suptitle(
        "TX right-wing syllable is the same kinematic prototype in every alphabet",
        fontsize=16 if dest == "slides" else 11,
        fontweight="bold",
        color=INK,
    )
    foot = (
        "Winner = max median Δp in pooled Wilcoxon at NOR_TX (same id for presence and novelty "
        "in 21/21 models). Grey = all model×id signatures. Blue = those 21 winners. "
        "cluster_id from HDBSCAN on kinematics (not portable raw_syllable_id). "
        "Cluster 13 = long, slow, crooked bouts (pause/still-like)."
    )
    fig_legend_and_footnote(fig, handles, foot, dest=dest)
    save_pdf_png(fig, out / "fig_da_tx_argmax_kinematics")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)
    out = args.out_dir or (args.da_dir / "figures")
    tests = pd.read_csv(args.da_dir / "da_syllable_tests_long.csv")
    proto = pd.read_csv(args.sig_dir / "syllable_prototypes_clustered.csv")
    w = tx_argmax_table(tests, proto)
    csv_path = args.da_dir / WINNER_CSV
    w.to_csv(csv_path, index=False)
    print(f"wrote {csv_path}  rows={len(w)}", flush=True)
    fig_argmax_kinematics(w, proto, out, dest=args.dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
