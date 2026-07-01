"""Tests for compile-bout-features manifest/tracking resolution."""

from __future__ import annotations

from pathlib import Path

import h5py
import pytest

from maze.kpms.apply_summary import resolve_tracking_h5_path
from maze.kpms.behavior_ethogram.compile import filter_manifests_with_results_h5
from maze.kpms.manifest_subset import SubsetConfig, load_manifests
from maze.pipeline.io.file_discovery import TrialManifest


def test_subset_config_skips_treatment_labels_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv_path = tmp_path / "manifest.csv"
    csv_path.write_text(
        "animal_id,session,trial,phase,sex,strain,tx\n"
        "3243,S01,T01,experimental,F,tg,RBSF\n",
        encoding="utf-8",
    )

    def _boom(*_args, **_kwargs):
        raise AssertionError("load_treatment_labels should not run")

    monkeypatch.setattr(
        "maze.kpms.manifest_subset.enrich_manifests_from_treatment_labels",
        lambda manifests, labels_path=None: _boom(),
    )
    cfg = SubsetConfig(manifest_csv=csv_path)
    manifests = load_manifests(cfg)
    assert len(manifests) == 1
    assert manifests[0].sex == "F"


def test_subset_config_enriches_when_opted_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv_path = tmp_path / "manifest.csv"
    csv_path.write_text(
        "animal_id,session,trial,phase\n" "3243,S01,T01,experimental\n",
        encoding="utf-8",
    )
    calls: list[int] = []

    def _enrich(manifests, labels_path=None):
        calls.append(len(manifests))
        for m in manifests:
            m.sex = "F"

    monkeypatch.setattr(
        "maze.kpms.manifest_subset.enrich_manifests_from_treatment_labels",
        _enrich,
    )
    cfg = SubsetConfig(manifest_csv=csv_path, enrich_from_treatment_labels=True)
    manifests = load_manifests(cfg)
    assert calls == [1]
    assert manifests[0].sex == "F"


def test_filter_manifests_with_results_h5(tmp_path: Path) -> None:
    results = tmp_path / "results_apply.h5"
    with h5py.File(results, "w") as h5:
        g = h5.create_group("3243-S01-T01")
        g.create_dataset("syllable", data=[0, 1, 1])

    m_hit = TrialManifest(animal_id="3243", session="S01", trial="T01", input_h5_path=str(tmp_path / "x.h5"))
    m_miss = TrialManifest(animal_id="9999", session="S01", trial="T01", input_h5_path=str(tmp_path / "y.h5"))
    out = filter_manifests_with_results_h5([m_hit, m_miss], results)
    assert [x.kpms_results_dict_key for x in out] == ["3243-S01-T01"]


def test_resolve_tracking_h5_prefers_explicit_path(tmp_path: Path) -> None:
    root = tmp_path / "test2"
    root.mkdir()
    explicit = root / "kpms_tracking.h5"
    explicit.write_bytes(b"\x00")
    other = root / "legacy.h5"
    other.write_bytes(b"\x00")
    resolved = resolve_tracking_h5_path(kpms_root=root, tracking_h5=explicit)
    assert resolved is None or resolved == explicit.resolve()
