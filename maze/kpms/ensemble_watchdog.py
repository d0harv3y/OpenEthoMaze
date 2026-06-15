"""Post-hoc and in-flight diagnostics for kpMS ensemble fit/apply artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

FIT_ARTIFACTS = (
    "checkpoint.h5",
    "results.h5",
    "fit_summary.json",
    "selected_trials.csv",
)
APPLY_ARTIFACTS = ("results_apply.h5", "apply_summary.json")
EXPECTED_FIT_ITERS = 250  # stage1 50 + stage2 200 (maze.kpms.fit.FitConfig defaults)

LOG_FAILURE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"RESOURCE_EXHAUSTED", re.I), "JAX/XLA resource exhausted (often RAM or VRAM OOM)"),
    (re.compile(r"Out of memory", re.I), "Explicit out-of-memory message"),
    (re.compile(r"GPU_0_bfc", re.I), "TensorFlow GPU allocator used (fit may not be on CPU)"),
    (re.compile(r"cuda", re.I), "CUDA/GPU mentioned in log (check JAX_PLATFORMS=cpu)"),
    (re.compile(r"XlaRuntimeError", re.I), "JAX XLA runtime error"),
    (re.compile(r"Killed", re.I), "Process killed (often Linux OOM killer)"),
    (re.compile(r"MemoryError", re.I), "Python MemoryError"),
)

STAGE2_START_HINT = re.compile(
    r"start_iter\s*=\s*50|start_iter=50|0%\|.*\|\s*0/201",
    re.I,
)


@dataclass
class ArtifactStatus:
    name: str
    present: bool
    size_bytes: int | None = None


@dataclass
class FitWatchdogReport:
    model_id: str
    model_dir: str
    log_path: str | None
    fit_complete: bool
    apply_present: bool
    artifacts: list[ArtifactStatus] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    clues: list[str] = field(default_factory=list)
    log_clues: list[str] = field(default_factory=list)
    checkpoint_iter: int | None = None
    median_bouts_results: float | None = None
    median_bouts_apply: float | None = None
    n_fit_trials_selected: int | None = None
    diagnosed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _artifact_status(model_dir: Path, name: str) -> ArtifactStatus:
    path = model_dir / name
    if not path.is_file():
        return ArtifactStatus(name=name, present=False)
    return ArtifactStatus(name=name, present=True, size_bytes=path.stat().st_size)


def _read_log_tail(log_path: Path | None, *, max_lines: int = 80) -> str:
    if log_path is None or not log_path.is_file():
        return ""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def _scan_log_clues(log_text: str) -> list[str]:
    if not log_text:
        return []
    clues: list[str] = []
    for pattern, message in LOG_FAILURE_PATTERNS:
        if pattern.search(log_text):
            clues.append(message)
    if STAGE2_START_HINT.search(log_text) and "RESOURCE_EXHAUSTED" in log_text.upper():
        clues.append(
            "Stage-2 full Gibbs likely OOM: stage-1 (AR-only, 50 iters) finished, "
            "then failure during continuous-state resampling (typical fused/seed_005 pattern)."
        )
    traceback_lines = [ln for ln in log_text.splitlines() if ln.startswith("  File ")]
    if traceback_lines:
        clues.append(f"Traceback frames: {traceback_lines[-1].strip()}")
    return list(dict.fromkeys(clues))


def _checkpoint_iteration(checkpoint_path: Path) -> int | None:
    if not checkpoint_path.is_file():
        return None
    try:
        import h5py
    except ImportError:
        return None
    try:
        with h5py.File(checkpoint_path, "r") as f:
            for key in ("iteration", "iter", "curr_iter", "n_iters"):
                if key in f.attrs:
                    return int(f.attrs[key])
            for group in ("model", "states"):
                if group in f and "iteration" in f[group].attrs:
                    return int(f[group].attrs["iteration"])
    except OSError:
        return None
    return None


def _median_bouts_from_h5(h5_path: Path) -> float | None:
    if not h5_path.is_file():
        return None
    try:
        import keypoint_moseq as kpms
    except ImportError:
        return None
    try:
        data = kpms.load_hdf5(str(h5_path))
    except OSError:
        return None
    counts: list[int] = []
    for rec in data.values():
        if not isinstance(rec, dict):
            continue
        syll = rec.get("syllable")
        if syll is None:
            continue
        arr = np.asarray(syll)
        if arr.size < 2:
            continue
        valid = (arr[:-1] >= 0) & (arr[1:] >= 0)
        counts.append(int(np.sum(valid & (arr[1:] != arr[:-1]))))
    if not counts:
        return None
    return float(np.median(counts))


def _selected_trial_count(model_dir: Path) -> int | None:
    csv_path = model_dir / "selected_trials.csv"
    if not csv_path.is_file():
        return None
    try:
        lines = csv_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if len(lines) <= 1:
        return 0
    return len(lines) - 1


def diagnose_model_dir(
    model_dir: Path,
    *,
    model_id: str | None = None,
    fit_log_path: Path | None = None,
    apply_log_path: Path | None = None,
    peer_median_bouts: float | None = None,
) -> FitWatchdogReport:
    """Inspect one ``<stream>/seed_NNN`` directory and optional fit/apply log."""
    model_dir = Path(model_dir)
    if model_id is None:
        model_id = model_dir.parent.name + "/" + model_dir.name

    artifacts = [_artifact_status(model_dir, name) for name in FIT_ARTIFACTS + APPLY_ARTIFACTS]
    by_name = {a.name: a for a in artifacts}
    fit_complete = all(by_name[n].present for n in FIT_ARTIFACTS)
    apply_present = by_name["results_apply.h5"].present

    issues: list[str] = []
    clues: list[str] = []

    if by_name["checkpoint.h5"].present and not by_name["fit_summary.json"].present:
        issues.append("incomplete_fit: checkpoint without fit_summary.json (fit did not finish)")
        ckpt_iter = _checkpoint_iteration(model_dir / "checkpoint.h5")
        if ckpt_iter is not None and ckpt_iter < EXPECTED_FIT_ITERS:
            clues.append(f"checkpoint iteration {ckpt_iter} < expected {EXPECTED_FIT_ITERS}")

    if apply_present and not fit_complete:
        issues.append(
            "partial_apply: results_apply.h5 exists but fit artifacts are incomplete "
            "(labels may be from a partial checkpoint)"
        )

    if not by_name["checkpoint.h5"].present:
        issues.append("missing_checkpoint")

    log_paths = [p for p in (fit_log_path, apply_log_path) if p is not None]
    log_clues: list[str] = []
    for lp in log_paths:
        log_clues.extend(_scan_log_clues(_read_log_tail(lp)))
    log_clues = list(dict.fromkeys(log_clues))
    if log_clues:
        clues.extend(log_clues)

    median_results = _median_bouts_from_h5(model_dir / "results.h5")
    median_apply = _median_bouts_from_h5(model_dir / "results_apply.h5")

    if median_apply is not None and peer_median_bouts is not None:
        if median_apply < 0.5 * peer_median_bouts:
            issues.append(
                f"low_segmentation: median bouts/trial {median_apply:.1f} "
                f"<< peer median {peer_median_bouts:.1f} (suspicious partial or bad fit)"
            )

    if by_name["fit_summary.json"].present:
        try:
            summary = json.loads((model_dir / "fit_summary.json").read_text(encoding="utf-8"))
            n_skipped = summary.get("n_skipped_recordings", 0)
            n_used = summary.get("n_used_recordings", 0)
            if n_used == 0:
                issues.append("fit_summary reports zero usable recordings")
            if n_skipped and n_used and n_skipped > n_used:
                clues.append(f"high skip rate: {n_skipped} skipped vs {n_used} used")
        except (OSError, json.JSONDecodeError):
            issues.append("fit_summary.json unreadable")

    return FitWatchdogReport(
        model_id=model_id,
        model_dir=str(model_dir),
        log_path=str(fit_log_path or apply_log_path) if (fit_log_path or apply_log_path) else None,
        fit_complete=fit_complete,
        apply_present=apply_present,
        artifacts=artifacts,
        issues=issues,
        clues=clues,
        log_clues=log_clues,
        checkpoint_iter=_checkpoint_iteration(model_dir / "checkpoint.h5"),
        median_bouts_results=median_results,
        median_bouts_apply=median_apply,
        n_fit_trials_selected=_selected_trial_count(model_dir),
    )


def diagnose_ensemble(
    project_root: Path,
    *,
    streams: tuple[str, ...],
    seeds: tuple[int, ...],
) -> list[FitWatchdogReport]:
    """Diagnose all ``<project_root>/<stream>/seed_NNN`` model dirs."""
    project_root = Path(project_root)
    fit_log_dir = project_root / "fit_logs"
    apply_log_dir = project_root / "apply_logs"

    entries: list[tuple[Path, str, Path | None, Path | None]] = []
    for stream in streams:
        for seed in seeds:
            model_name = f"seed_{seed:03d}"
            model_dir = project_root / stream / model_name
            if not model_dir.is_dir():
                continue
            fit_log = fit_log_dir / f"{stream}_{model_name}.log"
            apply_log = apply_log_dir / f"{stream}_{model_name}.log"
            entries.append(
                (
                    model_dir,
                    f"{stream}/{model_name}",
                    fit_log if fit_log.is_file() else None,
                    apply_log if apply_log.is_file() else None,
                )
            )

    pass1 = [
        diagnose_model_dir(
            model_dir,
            model_id=model_id,
            fit_log_path=fit_log,
            apply_log_path=apply_log,
        )
        for model_dir, model_id, fit_log, apply_log in entries
    ]
    peer_vals = [
        r.median_bouts_apply for r in pass1 if r.fit_complete and r.median_bouts_apply is not None
    ]
    peer_median = float(np.median(peer_vals)) if peer_vals else None
    if peer_median is None:
        return pass1

    return [
        diagnose_model_dir(
            Path(r.model_dir),
            model_id=r.model_id,
            fit_log_path=fit_log,
            apply_log_path=apply_log,
            peer_median_bouts=peer_median,
        )
        for r, (_, _, fit_log, apply_log) in zip(pass1, entries, strict=True)
    ]


def write_watchdog_report(
    reports: list[FitWatchdogReport],
    out_path: Path,
) -> Path:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_models": len(reports),
        "n_incomplete_fit": sum(1 for r in reports if not r.fit_complete),
        "n_with_issues": sum(1 for r in reports if r.issues),
        "models": [r.to_dict() for r in reports],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def print_watchdog_summary(reports: list[FitWatchdogReport]) -> None:
    print("\n=== kpMS ensemble watchdog ===")
    incomplete = [r for r in reports if not r.fit_complete]
    flagged = [r for r in reports if r.issues]
    print(f"Models scanned: {len(reports)}")
    print(f"Incomplete fits: {len(incomplete)}")
    print(f"With issues: {len(flagged)}")
    for report in flagged:
        print(f"\n--- {report.model_id} ---")
        for issue in report.issues:
            print(f"  ISSUE: {issue}")
        for clue in report.clues:
            print(f"  CLUE:  {clue}")
        if report.median_bouts_apply is not None:
            print(f"  median bouts/trial (apply): {report.median_bouts_apply:.1f}")
        if report.n_fit_trials_selected is not None:
            print(f"  fit trials selected: {report.n_fit_trials_selected}")
