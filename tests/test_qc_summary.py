"""qc_summary aggregation (Phase C8)."""

from __future__ import annotations

from pathlib import Path

import h5py

from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.qc_summary import (
    collect_qc_summary,
    export_qc_mistrial_csv,
    mistrial_action_hint,
)
from maze.pipeline.trial_quality import REASON_MISSING_VIDEO


def _write_trial(
    h5: h5py.File,
    key: TrialKey,
    *,
    mistrial_reason: str = "",
    with_ambulation: bool = False,
    qc_images: int = 0,
) -> None:
    g = h5.create_group(key.path().lstrip("/"))
    if mistrial_reason:
        g.attrs["mistrial_reason"] = mistrial_reason
    if with_ambulation:
        g.create_group("ambulation_metrics")
    if qc_images:
        g_qc = g.create_group("qc_images")
        for i in range(qc_images):
            g_qc.create_dataset(f"img_{i}", data=[1, 2, 3])


def test_collect_qc_summary_counts_and_mistrials(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    with h5py.File(db, "w") as h5:
        _write_trial(
            h5,
            TrialKey("1", "S01", "T01"),
            mistrial_reason=REASON_MISSING_VIDEO,
        )
        _write_trial(h5, TrialKey("1", "S01", "T02"), with_ambulation=True, qc_images=1)
        _write_trial(h5, TrialKey("1", "S01", "T03"))

    summary = collect_qc_summary(db)
    assert summary.total_trials == 3
    assert summary.mistrial_count == 1
    assert summary.analyzed_count == 1
    assert summary.pending_count == 1
    assert summary.with_qc_images_count == 1
    assert summary.reason_counts[REASON_MISSING_VIDEO] == 1
    assert len(summary.mistrial_rows) == 1
    assert summary.mistrial_rows[0].action_hint == mistrial_action_hint(REASON_MISSING_VIDEO)


def test_export_qc_mistrial_csv(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    with h5py.File(db, "w") as h5:
        _write_trial(
            h5,
            TrialKey("9", "S02", "T01"),
            mistrial_reason=REASON_MISSING_VIDEO,
        )
    summary = collect_qc_summary(db)
    out = export_qc_mistrial_csv(summary, tmp_path / "out" / "mistrial_summary.csv")
    text = out.read_text(encoding="utf-8")
    assert "missing_video" in text
    assert "action_hint" in text
    assert "9" in text
