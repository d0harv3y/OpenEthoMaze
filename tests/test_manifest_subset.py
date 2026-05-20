"""kpMS manifest_subset filters (Phase A A6)."""

from __future__ import annotations

from pathlib import Path

from maze.kpms.manifest_subset import SubsetConfig, filter_manifests

from conftest import make_manifest


def _sample_manifests() -> list:
    return [
        make_manifest(animal_id="1", sleap_path=Path("a.slp"), is_habituation=False),
        make_manifest(animal_id="2", sleap_path=None, is_habituation=False),
        make_manifest(animal_id="3", sleap_path=Path("b.slp"), is_habituation=True),
    ]


def test_filter_manifests_requires_sleap_by_default() -> None:
    cfg = SubsetConfig(include_habituation=True)
    out = filter_manifests(_sample_manifests(), cfg)
    assert [m.animal_id for m in out] == ["1", "3"]


def test_filter_manifests_excludes_habituation_when_disabled() -> None:
    cfg = SubsetConfig(include_habituation=False)
    out = filter_manifests(_sample_manifests(), cfg)
    assert [m.animal_id for m in out] == ["1"]


def test_filter_manifests_excludes_experimental_when_disabled() -> None:
    cfg = SubsetConfig(include_experimental=False, include_habituation=True)
    out = filter_manifests(_sample_manifests(), cfg)
    assert [m.animal_id for m in out] == ["3"]
