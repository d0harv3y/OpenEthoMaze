"""Aggregate QC / mistrial status across trials in a results HDF5 (Phase C8)."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..core.h5_layout import resolve_ambulation_metrics_group
from .db import list_trials, open_db
from .exports.csv_trials import _optional_filter_set, _trial_matches_export_filters
from .trial_quality import (
    REASON_FRAME_MISMATCH,
    REASON_MISSING_FRAME_COUNTS,
    REASON_MISSING_SLEAP,
    REASON_MISSING_VIDEO,
    REASON_NO_EXIT_XY,
    REASON_NO_TRACKING,
    REASON_PROCESSING_ERROR,
)

# Actionable hints keyed by mistrial_reason (and unknown codes).
MISTRIAL_ACTION_HINTS: dict[str, str] = {
    REASON_MISSING_VIDEO: (
        "Add or fix video_path (Pipeline → Discovery…, or sync manifest into trials.h5)."
    ),
    REASON_MISSING_FRAME_COUNTS: (
        "Re-run Discovery so video/H5 frame counts are recorded in the manifest."
    ),
    REASON_FRAME_MISMATCH: (
        "Align controller recording length with video (re-acquire or fix frame counts)."
    ),
    REASON_MISSING_SLEAP: (
        "Run Virtual acquisition… or place .slp/.predictions.slp beside the video."
    ),
    REASON_NO_TRACKING: (
        "Enable tracking during acquisition or run inference; need SLEAP or realtime xy in H5."
    ),
    REASON_PROCESSING_ERROR: (
        "Open trial in H5, check logs; re-run Analyze… after fixing inputs."
    ),
    REASON_NO_EXIT_XY: (
        "Set exit number/coords in controller H5 or analysis settings, then re-analyze."
    ),
}


def mistrial_action_hint(reason: str) -> str:
    """Return a short fix suggestion for a mistrial reason code."""
    code = (reason or "").strip()
    if not code:
        return ""
    return MISTRIAL_ACTION_HINTS.get(
        code,
        "See readme Analyze prefilter modes and trial_quality reason codes.",
    )


@dataclass(frozen=True)
class QcTrialRow:
    animal_id: str
    phase: str
    session: str
    trial: str
    mistrial_reason: str
    has_ambulation: bool
    qc_image_count: int

    @property
    def action_hint(self) -> str:
        return mistrial_action_hint(self.mistrial_reason)


@dataclass
class QcDbSummary:
    db_path: Path
    total_trials: int = 0
    analyzed_count: int = 0
    mistrial_count: int = 0
    pending_count: int = 0
    with_qc_images_count: int = 0
    reason_counts: dict[str, int] = field(default_factory=dict)
    mistrial_rows: list[QcTrialRow] = field(default_factory=list)


def _decode_reason(raw: object) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace").strip()
    return str(raw or "").strip()


def _trial_has_ambulation(g_trial: object) -> bool:
    return resolve_ambulation_metrics_group(g_trial) is not None


def _qc_image_count(g_trial: object) -> int:
    if "qc_images" not in g_trial:
        return 0
    try:
        return len(g_trial["qc_images"].keys())
    except Exception:
        return 0


def collect_qc_summary(
    db_path: Path | str,
    *,
    animal_ids: Optional[str] = None,
    sessions: Optional[str] = None,
    trial_names: Optional[str] = None,
) -> QcDbSummary:
    """
    Scan a results H5 and aggregate analyze / mistrial / QC-image status.

    ``pending`` trials have no ``mistrial_reason`` and no ``ambulation_metrics`` group.
    """
    db_path = Path(db_path)
    summary = QcDbSummary(db_path=db_path)
    f_aid = _optional_filter_set(animal_ids)
    f_sess = _optional_filter_set(sessions)
    f_trials = _optional_filter_set(trial_names)

    trials = list_trials(db_path)
    with open_db(db_path, "r") as h5:
        for key in trials:
            if not _trial_matches_export_filters(key, f_aid, f_sess, f_trials):
                continue
            summary.total_trials += 1
            try:
                g_trial = h5[key.path()]
            except Exception:
                summary.pending_count += 1
                continue

            reason = _decode_reason(g_trial.attrs.get("mistrial_reason", ""))
            has_amb = _trial_has_ambulation(g_trial)
            n_qc = _qc_image_count(g_trial)

            if has_amb:
                summary.analyzed_count += 1
            if n_qc > 0:
                summary.with_qc_images_count += 1

            if reason:
                summary.mistrial_count += 1
                summary.reason_counts[reason] = summary.reason_counts.get(reason, 0) + 1
                summary.mistrial_rows.append(
                    QcTrialRow(
                        animal_id=key.animal_id,
                        phase=key.phase,
                        session=key.session,
                        trial=key.trial,
                        mistrial_reason=reason,
                        has_ambulation=has_amb,
                        qc_image_count=n_qc,
                    )
                )
            elif not has_amb:
                summary.pending_count += 1

    summary.mistrial_rows.sort(
        key=lambda r: (r.mistrial_reason, r.animal_id, r.session, r.trial)
    )
    return summary


def format_qc_summary_text(summary: QcDbSummary) -> str:
    """Human-readable multi-line summary for dialogs and logs."""
    lines = [
        f"Database: {summary.db_path}",
        f"Trials (after filters): {summary.total_trials}",
        f"Analyzed (ambulation_metrics present): {summary.analyzed_count}",
        f"Mistrials (mistrial_reason set): {summary.mistrial_count}",
        f"Pending (not analyzed, not mistrial): {summary.pending_count}",
        f"With QC images: {summary.with_qc_images_count}",
    ]
    if summary.reason_counts:
        parts = [f"{r}: {c}" for r, c in sorted(summary.reason_counts.items())]
        lines.append("Mistrial reasons: " + ", ".join(parts))
    return "\n".join(lines)


def export_qc_mistrial_csv(
    summary: QcDbSummary,
    output_path: Path | str,
) -> Path:
    """Write mistrial rows from :func:`collect_qc_summary` to CSV."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "animal_id",
        "phase",
        "session",
        "trial",
        "mistrial_reason",
        "action_hint",
        "has_ambulation",
        "qc_image_count",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary.mistrial_rows:
            writer.writerow(
                {
                    "animal_id": row.animal_id,
                    "phase": row.phase,
                    "session": row.session,
                    "trial": row.trial,
                    "mistrial_reason": row.mistrial_reason,
                    "action_hint": row.action_hint,
                    "has_ambulation": row.has_ambulation,
                    "qc_image_count": row.qc_image_count,
                }
            )
    return output_path
