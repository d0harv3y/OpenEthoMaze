"""Majority-vote ensemble litmus for HITL strip."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from of_rear_classifier.mlp_ensemble import build_majority_pred_csv, majority_vote_labels


def test_majority_unanimous_and_tie_break_furkan():
    labs = {
        "Jin": np.array(["Supported", "None", "Grooming"], dtype=object),
        "Furkan": np.array(["Supported", "Unsupported", "Unsupported"], dtype=object),
        "Oliver": np.array(["Supported", "Unsupported", "Grooming"], dtype=object),
    }
    y, frac = majority_vote_labels(labs)
    assert list(y) == ["Supported", "Unsupported", "Grooming"]
    assert frac[0] == 1.0
    assert frac[1] == 2 / 3
    # Grooming 2 vs Unsupported 1
    assert frac[2] == 2 / 3


def test_build_majority_csv(tmp_path: Path):
    frames = np.arange(5)
    paths = {}
    for rater, seq in (
        ("Jin", ["None", "Supported", "Supported", "Grooming", "None"]),
        ("Furkan", ["None", "Supported", "Unsupported", "Grooming", "None"]),
        ("Oliver", ["None", "Supported", "Supported", "Unsupported", "None"]),
    ):
        p = tmp_path / f"pred_TestX_{rater}.csv"
        pd.DataFrame(
            {
                "frame": frames,
                "y_true": ["None"] * 5,
                "y_pred": seq,
                "covered": [0] * 5,
                "p_None": [0.7] * 5,
                "p_Supported": [0.1] * 5,
                "p_Unsupported": [0.1] * 5,
                "p_Grooming": [0.1] * 5,
            }
        ).to_csv(p, index=False, quoting=1)
        paths[rater] = p
    out = build_majority_pred_csv(paths, out_path=tmp_path / "pred_TestX_majority.csv")
    df = pd.read_csv(out)
    from of_rear_classifier.mlp_pred_io import _clean_label_series

    # pandas reads class name None as NaN — same as per-rater pred CSVs
    assert list(_clean_label_series(df["y_pred"])) == [
        "None",
        "Supported",
        "Supported",
        "Grooming",
        "None",
    ]
    assert "vote_frac" in df.columns
    assert "p_Supported" in df.columns
