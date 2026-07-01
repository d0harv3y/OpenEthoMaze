"""Tests for kpMS alignment memoization."""

from __future__ import annotations

import numpy as np
import pytest

from maze.kpms.frame_alignment import AlignedTrial, KpmsAlignmentCache, kpms_recording_key
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.io.file_discovery import TrialManifest


def _manifest(animal_id: str = "1") -> TrialManifest:
    return TrialManifest(
        animal_id=animal_id,
        session="S01",
        trial="T01",
        input_h5_path="x.h5",
    )


def test_alignment_cache_hits_on_second_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    aligned = AlignedTrial(
        recording_key="1-S01-T01",
        coordinates=np.zeros((5, 3, 2)),
        source_frame_indices=np.arange(5, dtype=np.int64),
    )

    def _fake_align(manifest, pre_cfg, **kwargs):
        calls["n"] += 1
        return aligned.recording_key, aligned.coordinates, aligned.source_frame_indices

    monkeypatch.setattr(
        "maze.kpms.frame_alignment.kpms_aligned_coordinates_and_indices",
        _fake_align,
    )
    cache = KpmsAlignmentCache()
    pre_cfg = KpmsPreprocessConfig()
    manifest = _manifest()
    assert cache.aligned_trial(manifest, pre_cfg) == aligned
    assert cache.aligned_trial(manifest, pre_cfg) == aligned
    assert calls["n"] == 1


def test_alignment_cache_preload_warms_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def _fake_align(manifest, pre_cfg, **kwargs):
        seen.append(kpms_recording_key(manifest))
        return (
            kpms_recording_key(manifest),
            np.zeros((3, 2, 2)),
            np.arange(3, dtype=np.int64),
        )

    monkeypatch.setattr(
        "maze.kpms.frame_alignment.kpms_aligned_coordinates_and_indices",
        _fake_align,
    )
    cache = KpmsAlignmentCache()
    manifests = [_manifest("1"), _manifest("2")]
    manifests[1].animal_id = "2"
    n = cache.preload(manifests, KpmsPreprocessConfig())
    assert n == 2
    assert len(seen) == 2
    assert len(cache) == 2


def test_alignment_cache_misses_when_preprocess_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def _fake_align(manifest, pre_cfg, **kwargs):
        calls["n"] += 1
        return (
            kpms_recording_key(manifest),
            np.zeros((2, 2, 2)),
            np.arange(2, dtype=np.int64),
        )

    monkeypatch.setattr(
        "maze.kpms.frame_alignment.kpms_aligned_coordinates_and_indices",
        _fake_align,
    )
    cache = KpmsAlignmentCache()
    manifest = _manifest()
    cfg_a = KpmsPreprocessConfig(px_per_cm=2.42)
    cfg_b = KpmsPreprocessConfig(px_per_cm=2.50)
    cache.aligned_trial(manifest, cfg_a)
    cache.aligned_trial(manifest, cfg_b)
    assert calls["n"] == 2
