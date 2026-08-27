"""Emit a compact JSON summary for the presence MI canvas (aggregates only)."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

DELTA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\paramscan_s1-1e8_s2-1e5_ss-50\presence"
    r"\mi_delta_presence_per_animal.csv"
)


def main() -> None:
    rows = list(csv.DictReader(DELTA.open(encoding="utf-8")))
    present = np.asarray([float(r["excess_present"]) for r in rows])
    absent = np.asarray([float(r["excess_absent"]) for r in rows])
    delta = np.asarray([float(r["delta_excess_present_minus_absent"]) for r in rows])
    _, pval = stats.wilcoxon(delta, alternative="two-sided")
    hist, edges = np.histogram(delta, bins=16)

    cells: dict[str, list[float]] = defaultdict(list)
    for r, d in zip(rows, delta):
        cells[f"{r['sex']}|{r['tx']}"].append(float(d))

    # scatter subsample for paired panel (all points is fine at 144)
    paired = [
        {
            "id": r["animal_id"],
            "sex": r["sex"],
            "tx": r["tx"],
            "absent": round(float(r["excess_absent"]), 4),
            "present": round(float(r["excess_present"]), 4),
            "delta": round(float(r["delta_excess_present_minus_absent"]), 4),
        }
        for r in rows
    ]

    payload = {
        "n": len(rows),
        "median_present": round(float(np.median(present)), 4),
        "median_absent": round(float(np.median(absent)), 4),
        "median_delta": round(float(np.median(delta)), 4),
        "mean_delta": round(float(np.mean(delta)), 4),
        "frac_pos": round(float(np.mean(delta > 0)), 4),
        "wilcoxon_p": float(pval),
        "hist_counts": [int(x) for x in hist],
        "hist_centers": [round(float(0.5 * (a + b)), 4) for a, b in zip(edges[:-1], edges[1:])],
        "cell_medians": {
            k: {"n": len(v), "median": round(float(np.median(v)), 4)}
            for k, v in sorted(cells.items())
        },
        "paired": paired,
        "figure_pdf": str(DELTA.parent / "fig_presence_excess_mi.pdf"),
        "figure_png": str(DELTA.parent / "fig_presence_excess_mi.png"),
    }
    out = DELTA.parent / "_canvas_payload.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
