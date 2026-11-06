from __future__ import annotations

import numpy as np

from of_rear_classifier.syllable_bouts import bouts_from_syllable_sequence, bouts_to_sturman_intervals


def test_bouts_from_sequence():
    s = np.array([1, 1, 1, 2, 2, 0, 0, 0, 0], dtype=int)
    df = bouts_from_syllable_sequence(s)
    assert len(df) == 3
    assert list(df["syllable_id"]) == [1, 2, 0]
    assert list(df["t0_frame"]) == [0, 3, 5]
    assert list(df["t1_frame"]) == [2, 4, 8]


def test_source_frame_remap():
    s = np.array([7, 7, 8], dtype=int)
    src = np.array([100, 101, 105], dtype=int)
    df = bouts_from_syllable_sequence(s, source_frame_indices=src)
    assert df.iloc[0]["t0_frame"] == 100
    assert df.iloc[0]["t1_frame"] == 101
    assert df.iloc[1]["t0_frame"] == 105


def test_sturman_export():
    s = np.array([1, 1, 2, 2], dtype=int)
    df = bouts_from_syllable_sequence(s)
    assert len(df) == 2
    df.loc[0, "label"] = "Supported"
    df.loc[1, "label"] = "Unsupported"
    out = bouts_to_sturman_intervals(df, fps=25.0, video_id="Test 27")
    assert len(out) == 2
    assert out.iloc[0]["type"] == "Supported"
