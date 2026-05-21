"""kpMS fit run config (Phase C C4) — no GPU / keypoint_moseq required for core tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from maze.kpms.fit_config import KpmsFitRunConfig, subset_config_from_fit_run


def test_subset_config_from_fit_run() -> None:
    cfg = KpmsFitRunConfig(
        project_dir=Path("/data/kpms"),
        manifest_csv=Path("/data/trial_manifest.csv"),
        max_trials=50,
        exclude_experimental=True,
        balance_columns=("sex", "tx"),
    )
    sub = subset_config_from_fit_run(cfg)
    assert sub.manifest_csv == Path("/data/trial_manifest.csv")
    assert sub.max_trials == 50
    assert sub.include_experimental is False
    assert sub.balance_columns == ("sex", "tx")


def test_fit_run_config_from_args() -> None:
    pytest.importorskip("keypoint_moseq")
    from maze.kpms.fit import fit_run_config_from_args

    class Args:
        project_dir = "/proj"
        model_name = "m1"
        manifest_csv = "man.csv"
        max_trials = 10
        random_seed = 7
        include_habituation = True
        exclude_experimental = False
        balance_by = "sex,phase"
        no_enrich_labels = True
        force_new = True

    cfg = fit_run_config_from_args(Args())  # type: ignore[arg-type]
    assert cfg.project_dir == Path("/proj")
    assert cfg.force_new is True
    assert cfg.enrich_from_treatment_labels is False
    assert cfg.balance_columns == ("sex", "phase")
