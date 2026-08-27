"""Tests for ladder Wilcoxon long-form + out_dir name parsing."""

from __future__ import annotations

from nor_object_mi.condition_ladder import ladder_tests_long, ladder_wilcoxon_steps_long
from nor_object_mi.restack_condition_ladder_long import parse_out_dir_name


def _animal(aid: str, sex: str, tx: str, *, d_fam: float) -> dict:
    # Construct ladder row where identical->fam_obj Δ = d_fam
    base = 0.1
    return {
        "animal_id": aid,
        "sex": sex,
        "tx": tx,
        "cohort": "c",
        "phase_layer": "NOR_TX",
        "nvl_nearest_hist_locus": "a",
        "fam_nearest_hist_locus": "b",
        "excess_no_obj_fam_side": base,
        "excess_identical_fam_side": base,
        "excess_fam_obj": base + d_fam,
        "excess_no_obj_nvl_side": base,
        "excess_identical_nvl_side": base,
        "excess_nvl_obj": base,
    }


def test_parse_out_dir_names() -> None:
    assert parse_out_dir_name("condition_ladder") == {
        "phase_layer": "NOR_TX",
        "symbol_kind": "syllable",
        "pattern_len": 1,
        "cleanup": "raw",
        "top_m": "",
    }
    assert parse_out_dir_name("condition_ladder_NOR_BL_clean")["cleanup"] == "clean"
    assert parse_out_dir_name("condition_ladder_ngram_n2_top50_clean") == {
        "phase_layer": "NOR_TX",
        "symbol_kind": "ngram",
        "pattern_len": 2,
        "cleanup": "clean",
        "top_m": 50,
    }
    assert parse_out_dir_name("not_a_ladder") is None


def test_wilcoxon_long_has_pooled_and_within_sex() -> None:
    rows = [
        _animal("a1", "F", "noSD", d_fam=0.2),
        _animal("a2", "F", "GHSD", d_fam=0.15),
        _animal("a3", "M", "noSD", d_fam=-0.05),
        _animal("a4", "M", "RBSD", d_fam=-0.02),
    ]
    w = ladder_wilcoxon_steps_long(rows)
    sexes = {(r["panel"], r["step"], r["sex"]) for r in w}
    assert ("fam", "identical->fam_obj", "all") in sexes
    assert ("fam", "identical->fam_obj", "F") in sexes
    assert ("fam", "identical->fam_obj", "M") in sexes
    all_tests = ladder_tests_long(rows)
    assert any(r["test"] == "kruskal" for r in all_tests)
    assert any(r["test"] == "wilcoxon_signed_rank" and r["sex"] == "all" for r in all_tests)
