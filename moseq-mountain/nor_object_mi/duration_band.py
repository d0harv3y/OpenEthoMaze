"""Identify the high-frequency long-duration syllable on inventory heatmaps.

Within each model, among bout-count frequency ranks 0..MAX_FREQ_RANK, pick the
syllable with the longest median bout. Ids are not portable; join HDBSCAN
cluster_id and TX DA argmax separately.
"""

from __future__ import annotations

import pandas as pd

MAX_FREQ_RANK = 15


def pick_duration_band(
    counts: pd.DataFrame, *, max_freq_rank: int = MAX_FREQ_RANK
) -> pd.DataFrame:
    """One row per model: duration peak among high-frequency ranks.

    ``counts`` needs: model, syllable, freq_rank, median_bout_frames, occupancy, n_bouts.
    """
    need = {
        "model",
        "syllable",
        "freq_rank",
        "median_bout_frames",
        "occupancy",
        "n_bouts",
    }
    missing = need - set(counts.columns)
    if missing:
        raise ValueError(f"counts missing {sorted(missing)}")
    rows: list[dict[str, object]] = []
    for model, g in counts.groupby("model", sort=True):
        hi = g[pd.to_numeric(g["freq_rank"], errors="coerce") <= max_freq_rank]
        if hi.empty:
            continue
        peak = hi.loc[hi["median_bout_frames"].idxmax()]
        rest = hi[hi["syllable"] != peak["syllable"]]
        neighbor = (
            float(rest["median_bout_frames"].median()) if len(rest) else float("nan")
        )
        occ_order = g.sort_values(["occupancy", "syllable"], ascending=[False, True])
        occ_rank = int((occ_order["syllable"].to_numpy() == int(peak["syllable"])).argmax())
        rows.append(
            {
                "model": str(model),
                "raw_syllable_id": int(peak["syllable"]),
                "freq_rank": int(peak["freq_rank"]),
                "occupancy_rank": occ_rank,
                "median_bout_frames": float(peak["median_bout_frames"]),
                "neighbor_median_bout_frames": neighbor,
                "duration_gap_frames": float(peak["median_bout_frames"]) - neighbor,
                "occupancy": float(peak["occupancy"]),
                "n_bouts": int(peak["n_bouts"]),
            }
        )
    return pd.DataFrame(rows)
