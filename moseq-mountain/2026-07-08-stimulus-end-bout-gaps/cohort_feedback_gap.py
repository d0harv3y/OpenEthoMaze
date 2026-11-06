"""Check feedback vs tracking length mismatch across trials."""
from __future__ import annotations

from pathlib import Path

import h5py

from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import load_manifest_csv

TRACKING_H5 = Path(r"C:\Users\admin\Documents\work\sack\vast_results_legacy.h5")
MANIFEST = Path(r"C:\Users\admin\Documents\work\sack\gerstner_vast_fit\gerstner_trial_manifest_kpms_fit.csv")


def main() -> None:
    manifests = load_manifest_csv(MANIFEST)
    gaps: list[int] = []
    checked = 0
    with h5py.File(TRACKING_H5, "r") as h5:
        for m in manifests:
            key = TrialKey.from_manifest(m)
            path = key.path().lstrip("/")
            if path not in h5:
                continue
            g = h5[path]
            n_xy = None
            for pt in ("spot_hybrid", "spot", "centroid"):
                try:
                    n_xy = len(g["ambulation_metrics"][pt]["xy"])
                    break
                except KeyError:
                    continue
            if n_xy is None:
                continue
            n_fb = 0
            if "feedback" in g and "table" in g["feedback"]:
                n_fb = len(g["feedback"]["table"])
            if n_fb == 0:
                continue
            checked += 1
            gaps.append(n_xy - n_fb)
    print(f"trials checked: {checked}")
    if gaps:
        import statistics as stats

        print(f"xy - feedback row gap: min={min(gaps)} median={stats.median(gaps):.0f} max={max(gaps)}")
        print(f"trials with gap>0: {sum(1 for g in gaps if g > 0)} ({100 * sum(1 for g in gaps if g > 0) / len(gaps):.1f}%)")


if __name__ == "__main__":
    main()
