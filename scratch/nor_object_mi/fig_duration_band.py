"""Map the inventory heatmap duration-band to cluster_id 13 and TX DA argmax.

Pick = longest median bout among bout-count frequency ranks 0..15 (the circled
high-frequency pale stripe). Ids are not portable.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_duration_band.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt

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
from nor_object_mi.duration_band import MAX_FREQ_RANK, pick_duration_band  # noqa: E402

DEFAULT_COUNTS = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_syllable_descriptives\syllable_counts_clean.csv"
)
DEFAULT_PROTO = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures\syllable_prototypes_clustered.csv"
)
DEFAULT_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
K_COLOR = {50: "#1b9e77", 75: "#d95f02", 100: "#7570b3"}


def _ss(model: str) -> int:
    m = re.search(r"ss-(\d+)$", str(model))
    return int(m.group(1)) if m else -1


def _info_md(n: int, n_c13: int, n_da: int) -> str:
    return f"""# INFO — inventory duration band vs TX DA

Question: is the pale high-frequency stripe on the syllable-descriptives
median-duration heatmaps (absorb <3) the same behavior across 21 kpMS models,
and is it the NOR_TX pooled DA volcano argmax?

## Pick (executable)

Per model, among `freq_rank` ≤ {MAX_FREQ_RANK} (bout-count rank, 0 = most used),
take the syllable with max `median_bout_frames`. Rare long syllables at rank >15
are excluded on purpose (that is the circle).

## Result (this run)

| Check | n / {n} |
|-------|---------|
| HDBSCAN `cluster_id` = 13 | {n_c13} |
| same `raw_syllable_id` as TX novelty DA argmax | {n_da} |
| occupancy rank = 0 | always on this table |

Bout-count rank **shifts** (typically 0–6). Occupancy rank does not: this
syllable is the frame hog. Neighbor high-frequency syllables are ~7–16 frame
medians; the pick is ~26–33 frames (~1.5–1.8 s mean duration in signatures).

## Inputs

| File | Role |
|------|------|
| `syllable_counts_clean.csv` | heatmap source (absorb <3) |
| `syllable_prototypes_clustered.csv` | kinematics + `cluster_id` |
| `tx_pooled_argmax_syllable.csv` | TX novelty DA winner |

`raw_syllable_id` is not portable.
"""


def join_band(
    counts: pd.DataFrame, proto: pd.DataFrame, winners: pd.DataFrame
) -> pd.DataFrame:
    band = pick_duration_band(counts)
    p = proto.rename(columns={"raw_syllable_id": "syllable"})
    keep = [
        "model",
        "syllable",
        "cluster_id",
        "syllable_mean_duration_s",
        "syllable_sig_mean_speed_mps",
        "syllable_sig_mean_abs_dheading",
        "syllable_mean_straightness",
        "syllable_mean_net_dheading_rad",
        "syllable_sig_mean_nose_tail_m",
    ]
    proto_keep = [c for c in keep if c != "n_bouts"]
    band = band.merge(
        p[proto_keep],
        left_on=["model", "raw_syllable_id"],
        right_on=["model", "syllable"],
        how="left",
    )
    w = winners[
        (winners["phase_layer"] == "NOR_TX") & (winners["step"] == "identical->novel")
    ][["model", "raw_syllable_id", "cluster_id", "median_delta_p", "hit_fdr05"]].rename(
        columns={
            "raw_syllable_id": "da_raw_syllable_id",
            "cluster_id": "da_cluster_id",
            "median_delta_p": "da_median_delta_p",
            "hit_fdr05": "da_hit_fdr05",
        }
    )
    out = band.merge(w, on="model", how="left")
    out["ss"] = out["model"].map(_ss)
    out["id_equals_da"] = out["raw_syllable_id"] == out["da_raw_syllable_id"]
    out["cluster13"] = out["cluster_id"] == 13
    return out.drop(columns=["syllable"], errors="ignore")


def fig_band(joined: pd.DataFrame, proto: pd.DataFrame, out: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    j = joined.copy()
    j["ss"] = j["ss"].astype(int)
    colors = [K_COLOR.get(int(s), INK) for s in j["ss"]]

    axes[0].scatter(j["freq_rank"], j["median_bout_frames"], c=colors, s=48, edgecolors=INK, linewidths=0.4, zorder=3)
    axes[0].axhline(j["neighbor_median_bout_frames"].median(), color="#888", ls="--", lw=0.8)
    axes[0].set_xlabel("bout-count frequency rank (0 = most used)")
    axes[0].set_ylabel("median bout duration (frames)")
    axes[0].set_title("A  rank shifts; duration does not", loc="left", fontweight="bold", color=INK)
    axes[0].set_xlim(-0.5, 8)

    axes[1].scatter(
        proto["syllable_mean_duration_s"],
        proto["syllable_sig_mean_speed_mps"],
        s=8,
        c="#c8c8c8",
        alpha=0.35,
        edgecolors="none",
        zorder=1,
    )
    axes[1].scatter(
        j["syllable_mean_duration_s"],
        j["syllable_sig_mean_speed_mps"],
        s=48,
        c=colors,
        edgecolors=INK,
        linewidths=0.4,
        zorder=3,
    )
    axes[1].set_xlabel("mean bout duration (s)")
    axes[1].set_ylabel("mean speed (m/s)")
    axes[1].set_title("B  timing × speed", loc="left", fontweight="bold", color=INK)

    axes[2].scatter(
        proto["syllable_mean_straightness"],
        proto["syllable_sig_mean_abs_dheading"],
        s=8,
        c="#c8c8c8",
        alpha=0.35,
        edgecolors="none",
        zorder=1,
    )
    axes[2].scatter(
        j["syllable_mean_straightness"],
        j["syllable_sig_mean_abs_dheading"],
        s=48,
        c=colors,
        edgecolors=INK,
        linewidths=0.4,
        zorder=3,
    )
    axes[2].set_xlabel("straightness")
    axes[2].set_ylabel("mean |Δheading| (rad/frame)")
    axes[2].set_title("C  path × heading", loc="left", fontweight="bold", color=INK)

    n_c13 = int(j["cluster13"].sum())
    n_da = int(j["id_equals_da"].sum())
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=K_COLOR[k], markersize=8, label=f"K={k}")
        for k in (50, 75, 100)
    ] + [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#c8c8c8", markersize=8, label="all prototypes"),
    ]
    fig_legend_and_footnote(
        fig,
        handles,
        (
            f"Duration-band pick = max median bout among freq_rank≤{MAX_FREQ_RANK}. "
            f"cluster_id=13 in {n_c13}/{len(j)}; same id as TX novelty DA argmax in {n_da}/{len(j)}. "
            "Dashed line in A = median of other high-frequency syllables' median durations. "
            "Grey in B–C = all model×syllable prototypes. Ids are not portable."
        ),
        dest=dest,
    )
    save_pdf_png(fig, out / "fig_duration_band_vs_da")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--counts", type=Path, default=DEFAULT_COUNTS)
    ap.add_argument("--proto", type=Path, default=DEFAULT_PROTO)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    out = args.out_dir or (args.da_dir)
    counts = pd.read_csv(args.counts)
    proto = pd.read_csv(args.proto)
    winners = pd.read_csv(args.da_dir / "tx_pooled_argmax_syllable.csv")
    joined = join_band(counts, proto, winners)
    joined.to_csv(out / "duration_band_vs_da.csv", index=False)
    n = len(joined)
    n_c13 = int(joined["cluster13"].sum())
    n_da = int(joined["id_equals_da"].sum())
    (out / "INFO_duration_band.md").write_text(_info_md(n, n_c13, n_da), encoding="utf-8")
    fig_band(joined, proto, out, dest=args.dest)
    summary = {
        "n_models": n,
        "n_cluster13": n_c13,
        "n_id_equals_da": n_da,
        "freq_rank_min": int(joined["freq_rank"].min()),
        "freq_rank_max": int(joined["freq_rank"].max()),
        "occupancy_rank_all_zero": bool((joined["occupancy_rank"] == 0).all()),
        "median_bout_frames_median": float(joined["median_bout_frames"].median()),
        "neighbor_median_bout_frames_median": float(joined["neighbor_median_bout_frames"].median()),
        "mean_duration_s_min": float(joined["syllable_mean_duration_s"].min()),
        "mean_duration_s_max": float(joined["syllable_mean_duration_s"].max()),
        "mean_speed_mps_min": float(joined["syllable_sig_mean_speed_mps"].min()),
        "mean_speed_mps_max": float(joined["syllable_sig_mean_speed_mps"].max()),
    }
    (out / "duration_band_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
