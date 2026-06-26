"""Phase II locomotion tier logic (scratch, no GPU/H5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRATCH = Path(__file__).resolve().parents[1] / "scratch" / "kpms_ensemble_compare"
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from behavior_ethogram_phase_i import hdbscan_labels_path  # noqa: E402
from behavior_ethogram_phase_ii import (  # noqa: E402
    DEFAULT_LOCOMOTION_RULES,
    PrototypeLabelRow,
    assign_tier_from_scalars,
    build_token_tier_rows,
    calibrate_from_phase_i,
    compute_token_centroids,
    load_locomotion_rules_yaml,
    rule_matches,
    write_locomotion_rules_yaml,
    write_token_tiers_csv,
)


def _proto(
    *,
    seed: str = "042",
    raw_id: int = 1,
    cluster_id: int = 0,
    speed: float = 0.03,
    dheading: float = 0.08,
    ambiguous: bool = False,
) -> PrototypeLabelRow:
    return PrototypeLabelRow(
        seed=seed,
        raw_syllable_id=raw_id,
        cluster_id=cluster_id,
        mean_speed_mps=speed,
        mean_abs_dheading=dheading,
        frac_still=0.8,
        bout_speed_iqr=0.01,
        ambiguous=ambiguous,
    )


def test_rule_matches_still_and_fast_patterns() -> None:
    still_rule = next(r for r in DEFAULT_LOCOMOTION_RULES["rules"] if r["tier"] == "still")
    fast_rule = next(r for r in DEFAULT_LOCOMOTION_RULES["rules"] if r["tier"] == "fast_transit")
    assert rule_matches(mean_speed_mps=0.03, mean_abs_dheading=0.10, rule=still_rule)
    assert not rule_matches(mean_speed_mps=0.12, mean_abs_dheading=0.10, rule=still_rule)
    assert rule_matches(mean_speed_mps=0.25, mean_abs_dheading=0.10, rule=fast_rule)
    assert not rule_matches(mean_speed_mps=0.25, mean_abs_dheading=0.40, rule=fast_rule)


def test_assign_tier_from_scalars_priority() -> None:
    assert assign_tier_from_scalars(
        mean_speed_mps=0.03,
        mean_abs_dheading=0.08,
        rules_doc=DEFAULT_LOCOMOTION_RULES,
    ) == "still"
    assert assign_tier_from_scalars(
        mean_speed_mps=0.30,
        mean_abs_dheading=0.10,
        rules_doc=DEFAULT_LOCOMOTION_RULES,
    ) == "fast_transit"
    assert assign_tier_from_scalars(
        mean_speed_mps=0.12,
        mean_abs_dheading=0.45,
        rules_doc=DEFAULT_LOCOMOTION_RULES,
    ) == "turn_heavy"


def test_compute_token_centroids_and_build_token_tier_rows() -> None:
    prototypes = [
        _proto(raw_id=1, cluster_id=2, speed=0.04, dheading=0.08),
        _proto(raw_id=2, cluster_id=2, speed=0.06, dheading=0.12),
        _proto(raw_id=3, cluster_id=5, speed=0.22, dheading=0.10),
        _proto(raw_id=4, cluster_id=5, speed=0.18, dheading=0.14, ambiguous=True),
    ]
    centroids = compute_token_centroids(prototypes)
    assert centroids[2].mean_speed_mps == pytest.approx(0.05)
    assert centroids[2].n_prototypes == 2
    tier_by_cluster = {2: "still", 5: "fast_transit"}
    rows = build_token_tier_rows(prototypes, tier_by_cluster, centroids)
    by_id = {int(r["raw_syllable_id"]): r for r in rows}
    assert by_id[1]["tier"] == "still"
    assert by_id[3]["tier"] == "fast_transit"
    assert by_id[4]["tier"] == "ambiguous"


def test_yaml_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "locomotion_tiers.yaml"
    write_locomotion_rules_yaml(path, DEFAULT_LOCOMOTION_RULES)
    loaded = load_locomotion_rules_yaml(path)
    assert loaded["version"] == "v1"
    assert loaded["fallback_tier"] == "slow_explore"
    assert len(loaded["rules"]) == len(DEFAULT_LOCOMOTION_RULES["rules"])


def test_calibrate_from_phase_i_end_to_end(tmp_path: Path) -> None:
    phase_i = tmp_path / "behavior_ethogram" / "phase_i"
    header = (
        "seed,raw_syllable_id,cluster_id,T_s,T_max,n_pad_dims,mean_speed_mps,"
        "global_occupancy,n_instances,speed_index,frac_still,mean_abs_dheading,"
        "bout_speed_iqr,ambiguous\n"
    )
    rows_csv = (
        "042,1,0,8,8,0,0.03,0.1,4,0,0.9,0.08,0.01,0\n"
        "042,2,0,8,8,0,0.04,0.1,4,1,0.85,0.10,0.01,0\n"
        "042,3,1,8,8,0,0.22,0.1,4,2,0.2,0.12,0.02,0\n"
        "042,4,2,8,8,0,0.15,0.1,4,3,0.3,0.40,0.15,1\n"
    )
    labels_path = hdbscan_labels_path(phase_i, "anatomical")
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    labels_path.write_text(header + rows_csv, encoding="utf-8")

    token_rows, centroids, tier_by_cluster, summary = calibrate_from_phase_i(phase_i)
    assert len(token_rows) == 4
    assert summary["n_prototypes"] == 3
    assert tier_by_cluster[0] == "still"
    assert tier_by_cluster[1] == "fast_transit"
    by_id = {int(r["raw_syllable_id"]): r for r in token_rows}
    assert by_id[4]["tier"] == "ambiguous"
    assert centroids[0].n_prototypes == 2

    phase_ii = tmp_path / "behavior_ethogram" / "phase_ii"
    out = phase_ii / "token_tiers.csv"
    write_token_tiers_csv(out, token_rows)
    text = out.read_text(encoding="utf-8")
    assert "token_mean_speed_mps" in text.splitlines()[0]
    assert "still" in text
