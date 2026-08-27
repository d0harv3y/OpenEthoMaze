"""Frame-share vs bout-count DA Δp glance (TX novelty / presence).

Reads sibling run folders:
  simpler_first_da/              (frame_share)
  simpler_first_da_bout_count/   (bout_count)

Regen:
  uv run python scratch/nor_object_mi/fig_da_frame_vs_bout.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_DOUBLE,
    INK,
    MUTE,
    PHASE_SHORT,
    PHASES,
    apply_style,
    fig_footnote,
    save_png,
    type_scale,
)
from nor_object_mi.fig_simpler_first_da import (  # noqa: E402
    DEFAULT_SIG,
    LADDER_PHASE_TAG,
    LADDER_STEP_SHORT,
    UNMAPPED_CLUSTER,
    VOLCANO_STEPS,
    load_cluster_lookup,
)
from nor_object_mi.fig_simpler_first_syllable_signatures import (  # noqa: E402
    colors_for_cluster_ids,
)

DEFAULT_FRAME = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
DEFAULT_BOUT = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da_bout_count"
)


def join_weightings(frame_dir: Path, bout_dir: Path) -> pd.DataFrame:
    cols = ["model", "phase_layer", "step", "raw_syllable_id", "median_delta_p", "hit_fdr05"]
    fr = pd.read_csv(frame_dir / "da_syllable_tests_long.csv", usecols=cols)
    bt = pd.read_csv(bout_dir / "da_syllable_tests_long.csv", usecols=cols)
    fr = fr.rename(columns={"median_delta_p": "delta_p_frame", "hit_fdr05": "hit_frame"})
    bt = bt.rename(columns={"median_delta_p": "delta_p_bout", "hit_fdr05": "hit_bout"})
    keys = ["model", "phase_layer", "step", "raw_syllable_id"]
    return fr.merge(bt, on=keys, how="inner")


def attach_clusters(df: pd.DataFrame, sig_dir: Path) -> pd.DataFrame:
    proto = pd.read_csv(
        sig_dir / "syllable_prototypes_clustered.csv",
        usecols=["model", "raw_syllable_id", "cluster_id"],
    )
    out = df.merge(proto, on=["model", "raw_syllable_id"], how="left")
    cid = pd.to_numeric(out["cluster_id"], errors="coerce")
    out["cluster_id"] = cid.fillna(UNMAPPED_CLUSTER).astype(np.int64)
    return out


def fig_frame_vs_bout(
    joined: pd.DataFrame,
    out: Path,
    *,
    phase: str,
    step: str,
    dest: str,
    cluster_lookup: dict,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    step_lab = dict(VOLCANO_STEPS).get(step, step)
    sub = joined[(joined["phase_layer"] == phase) & (joined["step"] == step)].copy()
    fig, ax = plt.subplots(figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    cols = colors_for_cluster_ids(sub["cluster_id"], cluster_lookup)
    ax.scatter(
        sub["delta_p_frame"],
        sub["delta_p_bout"],
        s=10 if dest == "slides" else 6,
        c=cols,
        alpha=0.55,
        edgecolors="none",
        zorder=2,
    )
    c13 = sub[sub["cluster_id"] == 13]
    if not c13.empty:
        ax.scatter(
            c13["delta_p_frame"],
            c13["delta_p_bout"],
            s=36 if dest == "slides" else 18,
            facecolors="none",
            edgecolors=INK,
            linewidths=0.9,
            zorder=3,
            label="cluster 13",
        )
    lim = 0.15
    ax.plot([-lim, lim], [-lim, lim], color="#bbbbbb", lw=0.8, ls="--", zorder=0)
    ax.axhline(0.0, color="#dddddd", lw=0.6, zorder=0)
    ax.axvline(0.0, color="#dddddd", lw=0.6, zorder=0)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Δp frame_share (median across animals)")
    ax.set_ylabel("Δp bout_count (median across animals)")
    ax.set_title(
        f"{PHASE_SHORT[phase]} · {step_lab} · frame vs bout Δp",
        loc="left",
        fontweight="bold",
        color=INK,
        fontsize=ts["annotation"],
    )
    fig.suptitle(
        "Does bout-count weighting shrink the pause wing?",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    if not c13.empty:
        ax.legend(frameon=False, loc="upper left", fontsize=ts["legend"])
    fig_footnote(
        fig,
        (
            "One point = model × raw_syllable_id. Color = HDBSCAN cluster_id. "
            "Outlined = cluster 13. Diagonal = identity. Same animals/steps; only composition weight differs."
        ),
        fontsize=ts["footnote"],
        y=0.01,
        color=MUTE,
    )
    tag = LADDER_STEP_SHORT.get(step, step)
    save_png(fig, out / f"fig_da_frame_vs_bout_{LADDER_PHASE_TAG[phase]}_{tag}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frame-dir", type=Path, default=DEFAULT_FRAME)
    ap.add_argument("--bout-dir", type=Path, default=DEFAULT_BOUT)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    out = args.out_dir or (args.bout_dir / "figures")
    out.mkdir(parents=True, exist_ok=True)
    joined = attach_clusters(join_weightings(args.frame_dir, args.bout_dir), args.sig_dir)
    joined.to_csv(args.bout_dir / "da_frame_vs_bout_joined.csv", index=False)
    lookup, _ids, _listed = load_cluster_lookup(args.sig_dir)
    for phase in PHASES:
        for step, _lab in VOLCANO_STEPS:
            fig_frame_vs_bout(
                joined, out, phase=phase, step=step, dest=args.dest, cluster_lookup=lookup
            )
    print(f"wrote glance figures -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
