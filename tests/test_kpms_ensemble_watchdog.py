"""Tests for kpMS ensemble fit watchdog heuristics."""

from __future__ import annotations

from pathlib import Path

from maze.kpms.ensemble_watchdog import _scan_log_clues, diagnose_model_dir

FUSED_SEED_005_OOM_TAIL = """
Resampling z (discrete latent states)
Outputs will be saved to /home/data/test/fused/seed_005
  0%|                                           | 0/201 [00:00<?, ?it/s]
Allocator (GPU_0_bfc) ran out of memory trying to allocate 16.63GiB
RESOURCE_EXHAUSTED: Out of memory while trying to allocate 17860165768 bytes.
jaxlib._jax.XlaRuntimeError: RESOURCE_EXHAUSTED: Out of memory
"""


def test_scan_log_clues_detects_stage2_gpu_oom() -> None:
    clues = _scan_log_clues(FUSED_SEED_005_OOM_TAIL)
    assert any("resource exhausted" in c.lower() for c in clues)
    assert any("stage-2" in c.lower() or "stage-1" in c.lower() for c in clues)
    assert any("gpu" in c.lower() for c in clues)


def test_diagnose_incomplete_fit_with_partial_apply(tmp_path: Path) -> None:
    model_dir = tmp_path / "fused" / "seed_005"
    model_dir.mkdir(parents=True)
    (model_dir / "checkpoint.h5").write_bytes(b"\x00")
    (model_dir / "results_apply.h5").write_bytes(b"\x00")
    (model_dir / "selected_trials.csv").write_text("animal_id,session,trial\n", encoding="utf-8")

    log = tmp_path / "fit_logs" / "fused_seed_005.log"
    log.parent.mkdir(parents=True)
    log.write_text(FUSED_SEED_005_OOM_TAIL, encoding="utf-8")

    report = diagnose_model_dir(
        model_dir,
        model_id="fused/seed_005",
        fit_log_path=log,
    )
    assert not report.fit_complete
    assert report.apply_present
    assert any("incomplete_fit" in i for i in report.issues)
    assert any("partial_apply" in i for i in report.issues)
    assert report.log_clues
