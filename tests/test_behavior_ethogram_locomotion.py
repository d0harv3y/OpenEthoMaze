"""Unit tests for locomotion tier calibration."""

from __future__ import annotations

from pathlib import Path

import pytest

from maze.kpms.behavior_ethogram.locomotion import (
    DEFAULT_LOCOMOTION_RULES,
    BoutTokenRow,
    assign_bout_tiers,
    assign_tier_from_scalars,
    compute_token_centroids,
    load_locomotion_rules_yaml,
    rule_matches,
    tier_by_token_from_centroids,
    write_locomotion_rules_yaml,
)


def test_rule_matches_still_and_fast_patterns() -> None:
    still_rule = next(r for r in DEFAULT_LOCOMOTION_RULES["rules"] if r["tier"] == "still")
    fast_rule = next(r for r in DEFAULT_LOCOMOTION_RULES["rules"] if r["tier"] == "fast_transit")
    assert rule_matches(mean_speed_mps=0.03, mean_abs_dheading=0.10, rule=still_rule)
    assert not rule_matches(mean_speed_mps=0.12, mean_abs_dheading=0.10, rule=still_rule)
    assert rule_matches(mean_speed_mps=0.25, mean_abs_dheading=0.10, rule=fast_rule)


def test_assign_tier_from_scalars_priority() -> None:
    assert (
        assign_tier_from_scalars(
            mean_speed_mps=0.03,
            mean_abs_dheading=0.08,
            rules_doc=DEFAULT_LOCOMOTION_RULES,
        )
        == "still"
    )
    assert (
        assign_tier_from_scalars(
            mean_speed_mps=0.30,
            mean_abs_dheading=0.10,
            rules_doc=DEFAULT_LOCOMOTION_RULES,
        )
        == "fast_transit"
    )
    assert (
        assign_tier_from_scalars(
            mean_speed_mps=0.12,
            mean_abs_dheading=0.45,
            rules_doc=DEFAULT_LOCOMOTION_RULES,
        )
        == "turn_heavy"
    )


def test_compute_token_centroids_and_tier_assignment() -> None:
    rows = [
        BoutTokenRow("042", "k1", 0, 2, 0.04, 0.08, False, ""),
        BoutTokenRow("042", "k1", 1, 2, 0.06, 0.12, False, ""),
        BoutTokenRow("042", "k2", 0, 5, 0.22, 0.10, False, ""),
        BoutTokenRow("042", "k2", 1, 5, 0.18, 0.14, True, ""),
    ]
    centroids = compute_token_centroids(rows)
    assert centroids[2].mean_speed_mps == pytest.approx(0.05)
    tier_by_token = tier_by_token_from_centroids(centroids, DEFAULT_LOCOMOTION_RULES)
    assert tier_by_token[2] == "still"
    assert tier_by_token[5] == "fast_transit"
    tiered = assign_bout_tiers(rows, tier_by_token)
    assert tiered[-1].tier == "ambiguous"


def test_yaml_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "locomotion_tiers.yaml"
    write_locomotion_rules_yaml(path, DEFAULT_LOCOMOTION_RULES)
    loaded = load_locomotion_rules_yaml(path)
    assert loaded["version"] == "v1"
    assert loaded["fallback_tier"] == "slow_explore"
