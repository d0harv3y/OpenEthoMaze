"""Sturman DLC CSV → features smoke (skips if DLCAnalyzer OFT missing)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

OFT = Path(r"C:\Users\admin\code\DLCAnalyzer\data\OFT")
SAMPLE = OFT / "Output_DLC" / "3_01_A_190507121945DeepCut_resnet50_Blockcourse1May9shuffle1_1030000.csv"

pytestmark = pytest.mark.skipif(not SAMPLE.is_file(), reason="DLCAnalyzer OFT CSV not present")


def test_load_sturman_video_features_shape():
    from of_rear_classifier.sturman_dlc import load_sturman_video_features
    from of_rear_classifier.skeleton import N_FEATURES

    feat, meta = load_sturman_video_features(SAMPLE)
    assert feat.shape[1] == N_FEATURES
    assert feat.shape[0] == meta["n_frames"]
    assert meta["n_frames"] < meta["n_frames_raw"]
    assert np.all(np.isfinite(feat[:, :20]))  # z-scored continuous
