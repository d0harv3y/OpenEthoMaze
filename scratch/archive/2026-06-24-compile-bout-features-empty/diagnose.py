"""Diagnose compile-bout-features empty output on test2."""
from __future__ import annotations

from pathlib import Path

import h5py

from maze.kpms.frame_alignment import kpms_aligned_coordinates_and_indices, kpms_recording_key
from maze.kpms.manifest_subset import SubsetConfig, filter_manifests, load_manifests
from maze.kpms.preprocess import KpmsPreprocessConfig

MANIFEST = Path(r"C:\Users\admin\Documents\work\sack\test2\trial_manifest_kpms_tracking.csv")
RESULTS = Path(r"C:\Users\admin\Documents\work\sack\test2\anatomical\seed_042\results_apply.h5")


def main() -> None:
    cfg = SubsetConfig(manifest_csv=MANIFEST, require_sleap=True, enrich_from_treatment_labels=False)
    all_m = load_manifests(cfg)
    print("manifests loaded:", len(all_m))
    manifests = filter_manifests(all_m, cfg)
    print("manifests after filter:", len(manifests))

    pre = KpmsPreprocessConfig()
    db = Path(r"C:\Users\admin\Documents\work\sack\test2\kpms_tracking.h5")
    print("local tracking h5:", db.is_file())

    skip_pose = 0
    skip_hab = 0
    for m in all_m[:20]:
        from maze.kpms.manifest_subset import _manifest_has_usable_pose
        pose = _manifest_has_usable_pose(m, db if db.is_file() else Path())
        sleap_ok = m.sleap_path and Path(m.sleap_path).is_file()
        print(
            m.kpms_recording_key,
            "phase", m.phase,
            "has_tracking_pose", m.has_tracking_pose,
            "pose_ok", pose,
            "sleap_ok", sleap_ok,
        )
        if not pose:
            skip_pose += 1
        if m.phase == "habituation":
            skip_hab += 1
    print("first20 skip_pose", skip_pose, "habituation", skip_hab)

    with h5py.File(RESULTS) as h5:
        h5_keys = set(h5.keys())

    counts = {"no_key": 0, "no_align": 0, "len_mismatch": 0, "ok": 0}
    examples: dict[str, str] = {}
    for m in manifests:
        rk = kpms_recording_key(m)
        if rk not in h5_keys:
            counts["no_key"] += 1
            if "no_key" not in examples:
                examples["no_key"] = rk
            continue
        with h5py.File(RESULTS) as h5:
            z_len = len(h5[rk]["syllable"])
        al = kpms_aligned_coordinates_and_indices(m, pre)
        if al is None:
            counts["no_align"] += 1
            if "no_align" not in examples:
                examples["no_align"] = f"{rk} sleap={m.sleap_path}"
            continue
        if len(al[1]) != z_len:
            counts["len_mismatch"] += 1
            if "len_mismatch" not in examples:
                examples["len_mismatch"] = f"{rk} coord={len(al[1])} z={z_len}"
            continue
        counts["ok"] += 1

    print("counts:", counts)
    print("examples:", examples)


if __name__ == "__main__":
    main()
