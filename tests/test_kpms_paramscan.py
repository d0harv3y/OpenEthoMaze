"""kpMS param-scan grid and fit hyperparameter CLI wiring."""

from __future__ import annotations

from maze.kpms.fit_config import FitConfig
from maze.kpms.paramscan import (
    DEFAULT_STAGE1_KAPPA,
    NOR_NUM_STATES,
    NOR_STAGE2_KAPPA,
    VAST_CONF_THRESHOLDS,
    iter_vast_conf_paramscan_grid,
    kappa_token,
    paramscan_model_name,
)


def test_kappa_token_nor_values() -> None:
    assert kappa_token(1e4) == "1e4"
    assert kappa_token(3e4) == "3e4"
    assert kappa_token(1e5) == "1e5"
    assert kappa_token(1e8) == "1e8"


def test_paramscan_model_name_vast_conf_suffix() -> None:
    name = paramscan_model_name(
        stage1_kappa=1e8,
        stage2_kappa=3e4,
        num_states=75,
        conf_threshold=0.2,
    )
    assert name == "paramscan_s1-1e8_s2-3e4_ss-75_ct-0.2"


def test_vast_conf_grid_is_27_jobs() -> None:
    jobs = list(iter_vast_conf_paramscan_grid())
    assert len(jobs) == 27
    names = {j.model_name for j in jobs}
    assert len(names) == 27
    assert jobs[0].stage2_kappa == NOR_STAGE2_KAPPA[0]
    assert jobs[0].num_states == NOR_NUM_STATES[0]
    assert jobs[0].conf_threshold == VAST_CONF_THRESHOLDS[0]
    assert jobs[0].stage1_kappa == DEFAULT_STAGE1_KAPPA


def test_fit_run_config_hyperparams_from_args() -> None:
    from maze.kpms.fit import fit_run_config_from_args

    class Args:
        project_dir = "/proj"
        model_name = "paramscan_s1-1e8_s2-1e4_ss-50_ct-0.1"
        manifest_csv = "man.csv"
        max_trials = 0
        random_seed = 42
        include_habituation = True
        exclude_experimental = False
        balance_by = "sex,tx,phase,strain"
        no_enrich_labels = False
        force_new = True
        pose_stream = "anatomical"
        float32 = False
        stage1_kappa = 1e8
        stage2_kappa = 3e4
        num_states = 75
        conf_threshold = 0.3

    cfg = fit_run_config_from_args(Args())  # type: ignore[arg-type]
    assert cfg.fit.stage1_kappa == 1e8
    assert cfg.fit.stage2_kappa == 3e4
    assert cfg.fit.num_states == 75
    assert cfg.fit.conf_threshold == 0.3
    assert cfg.fit.seed == 42


def test_fit_run_config_defaults_when_hyperparams_omitted() -> None:
    from maze.kpms.fit import fit_run_config_from_args

    class Args:
        project_dir = "/proj"
        model_name = "orm_kpms_fit"
        manifest_csv = None
        max_trials = 300
        random_seed = 7
        include_habituation = False
        exclude_experimental = False
        balance_by = "sex"
        no_enrich_labels = False
        force_new = False
        pose_stream = "anatomical"
        float32 = False
        stage1_kappa = None
        stage2_kappa = None
        num_states = None
        conf_threshold = None

    cfg = fit_run_config_from_args(Args())  # type: ignore[arg-type]
    assert cfg.fit == FitConfig(seed=7)


def test_preprocess_config_carries_conf_threshold() -> None:
    from maze.kpms.preprocess import KpmsPreprocessConfig

    cfg = KpmsPreprocessConfig(conf_threshold=0.1)
    assert cfg.conf_threshold == 0.1


def test_param_sweep_plan_job_count(tmp_path) -> None:
    from maze.cli.kpms_param_sweep import _iter_jobs, _write_sweep_plan, parse_args

    manifest = tmp_path / "manifest.csv"
    manifest.write_text("animal_id,session,trial\n", encoding="utf-8")
    project = tmp_path / "vast_paramscan"
    args = parse_args(
        [
            "--project-dir",
            str(project),
            "--manifest-csv",
            str(manifest),
            "--dry-run",
        ]
    )
    jobs = _iter_jobs(args)
    assert len(jobs) == 27
    plan = _write_sweep_plan(args, jobs)
    assert plan.is_file()
    payload = plan.read_text(encoding="utf-8")
    assert '"n_jobs": 27' in payload
