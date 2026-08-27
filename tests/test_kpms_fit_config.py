"""kpMS fit run config (Phase C C4) — no GPU / keypoint_moseq required for core tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from maze.kpms.fit_config import KpmsFitRunConfig, subset_config_from_fit_run
from maze.kpms.project_paths import resolve_kpms_project_dir

_REPO_ROOT = Path(__file__).resolve().parents[1]


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
        pose_stream = "blob"
        float32 = True
        stage1_kappa = None
        stage2_kappa = None
        num_states = None
        conf_threshold = None

    cfg = fit_run_config_from_args(Args())  # type: ignore[arg-type]
    assert cfg.project_dir == Path("/proj")
    assert cfg.pose_stream == "blob"
    assert cfg.force_new is True
    assert cfg.use_float32 is True
    assert cfg.enrich_from_treatment_labels is False
    assert cfg.balance_columns == ("sex", "phase")
    assert cfg.fit.seed == 7
    assert resolve_kpms_project_dir(cfg.project_dir, cfg.pose_stream) == Path(
        "/proj/blob"
    )


def test_write_json_serializes_path(tmp_path: Path) -> None:
    import json

    from maze.kpms.io import write_json

    db = tmp_path / "kpms_tracking.h5"
    out = tmp_path / "summary.json"
    write_json(out, {"db_path": db})
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["db_path"] == str(db)


def test_prepare_results_path_removes_stale_file(tmp_path: Path) -> None:
    pytest.importorskip("keypoint_moseq")
    from maze.kpms.fit import _prepare_results_path

    results = tmp_path / "results.h5"
    results.write_bytes(b"stale")
    _prepare_results_path(results, force_new=False)
    assert not results.is_file()


def test_fit_cli_pose_stream_help() -> None:
    pytest.importorskip("keypoint_moseq")
    proc = subprocess.run(
        ["uv", "run", "maze-kpms-fit", "--help"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--pose-stream" in proc.stdout
    assert "--float32" in proc.stdout
    assert "--stage2-kappa" in proc.stdout
    assert "--conf-threshold" in proc.stdout
    assert "fused" in proc.stdout


def test_apply_run_config_from_args_pose_stream() -> None:
    pytest.importorskip("keypoint_moseq")
    from maze.kpms.apply import apply_run_config_from_args

    class Args:
        project_dir = "/kpms_root"
        model_name = "orm_kpms_fit"
        manifest_csv = "man.csv"
        results_path = None
        animal_id = None
        session = None
        trial = None
        include_habituation = False
        exclude_experimental = False
        no_enrich_labels = False
        num_iters = 50
        no_reindex = False
        no_overwrite_results = False
        quiet = False
        pose_stream = "fused"

    cfg = apply_run_config_from_args(Args())  # type: ignore[arg-type]
    assert cfg.pose_stream == "fused"
    assert resolve_kpms_project_dir(cfg.project_dir, cfg.pose_stream) == Path(
        "/kpms_root/fused"
    )


def test_apply_cli_pose_stream_help() -> None:
    pytest.importorskip("keypoint_moseq")
    proc = subprocess.run(
        ["uv", "run", "maze-kpms-apply", "--help"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--pose-stream" in proc.stdout
    assert "anatomical" in proc.stdout
