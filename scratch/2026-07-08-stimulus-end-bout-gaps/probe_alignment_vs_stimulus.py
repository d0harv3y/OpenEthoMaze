"""Compare kpMS alignment tail vs controller stimulus array lengths for one trial."""
from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from maze.kpms.behavior_ethogram.stimulus_join import read_trial_stimulus_frames
from maze.kpms.frame_alignment import kpms_aligned_coordinates_and_indices
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest, load_manifest_csv

KPMS_ROOT = Path(r"C:\Users\admin\Documents\work\sack\gerstner_vast_fit")
MANIFEST = KPMS_ROOT / "gerstner_trial_manifest_kpms_fit.csv"
TRACKING_H5 = Path(r"C:\Users\admin\Documents\work\sack\vast_results_legacy.h5")
RESULTS_H5 = KPMS_ROOT / "results.h5"
TRIAL_KEY = "3245-S01-T01"


def main() -> None:
    manifests = {m.kpms_results_dict_key: m for m in load_manifest_csv(MANIFEST)}
    manifest = manifests[TRIAL_KEY]
    pre_cfg = KpmsPreprocessConfig(db_path=TRACKING_H5)

    aligned = kpms_aligned_coordinates_and_indices(manifest, pre_cfg)
    if aligned is None:
        print("no alignment")
        return
    _rk, _coord, src_idx = aligned
    src = np.asarray(src_idx, dtype=np.int64)
    print(f"kpMS aligned rows: {len(src)}")
    print(f"source_frame_indices: min={src.min()} max={src.max()} unique={len(np.unique(src))}")

    trial_key = TrialKey.from_manifest(manifest)
    with h5py.File(TRACKING_H5, "r") as h5:
        g = h5[trial_key.path().lstrip("/")]
        stim = read_trial_stimulus_frames(g)
    assert stim is not None
    n_stim = len(stim.motor_fb)
    print(f"stimulus arrays length (min feedback/xy): {n_stim}")
    print(f"motor_fb finite: {np.isfinite(stim.motor_fb).sum()} / {n_stim}")
    print(f"dist finite: {np.isfinite(stim.dist_to_exit_px).sum()} / {n_stim}")

    oob = src >= n_stim
    neg = src < 0
    print(f"kpMS rows with src_idx >= n_stim: {oob.sum()} ({100 * oob.mean():.1f}%)")
    print(f"kpMS rows with src_idx < 0: {neg.sum()}")

    if np.any(oob):
        first_oob = int(np.flatnonzero(oob)[0])
        print(f"first OOB kpMS row: {first_oob} src={src[first_oob]}")
        print(f"last in-range row: {first_oob - 1} src={src[first_oob - 1]}")

    # Tail of source indices
    print("\nlast 10 source_frame_indices:", src[-10:].tolist())

    with h5py.File(RESULTS_H5, "r") as h5:
        if TRIAL_KEY in h5:
            syll = np.asarray(h5[TRIAL_KEY]["syllable"], dtype=np.int64)
            print(f"\nresults.h5 syllable rows: {len(syll)}")
            print(f"syllable len == aligned len: {len(syll) == len(src)}")

    # Per-point xy lengths in trial H5
    with h5py.File(TRACKING_H5, "r") as h5:
        g = h5[trial_key.path().lstrip("/")]
        for pt in ("spot_hybrid", "spot", "center", "centroid"):
            path = f"ambulation_metrics/{pt}/xy"
            parts = path.split("/")
            cur = g
            ok = True
            for p in parts:
                if p not in cur:
                    ok = False
                    break
                cur = cur[p]
            if ok:
                print(f"xy table {pt}: {len(cur)} rows")
        gfb = g.get("feedback")
        if gfb is not None and "table" in gfb:
            print(f"feedback/table: {len(gfb['table'])} rows")


if __name__ == "__main__":
    main()
