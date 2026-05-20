"""kpMS apply filter helpers (Phase A A6)."""

from __future__ import annotations

from maze.kpms.apply import expand_filter_arg, filter_manifests_by_trial_selectors

from conftest import make_manifest


def test_expand_filter_arg_splits_commas_and_spaces() -> None:
    assert expand_filter_arg(["a, b", "c"]) == ["a", "b", "c"]
    assert expand_filter_arg(None) is None
    assert expand_filter_arg([""]) is None


def test_filter_manifests_by_trial_selectors_and_across_dimensions() -> None:
    manifests = [
        make_manifest(animal_id="556", session="S01", trial="T01"),
        make_manifest(animal_id="556", session="S02", trial="T01"),
        make_manifest(animal_id="557", session="S01", trial="T02"),
    ]
    by_animal = filter_manifests_by_trial_selectors(manifests, ["556"], None, None)
    assert len(by_animal) == 2
    by_session = filter_manifests_by_trial_selectors(manifests, None, ["S01"], None)
    assert len(by_session) == 2
    by_all = filter_manifests_by_trial_selectors(manifests, ["557"], ["S01"], ["T02"])
    assert len(by_all) == 1
    assert by_all[0].animal_id == "557"
