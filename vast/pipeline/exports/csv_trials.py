"""CSV export for VAST: long-format metrics with trial_state and trajectory_source."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import csv
import math
import numpy as np

from ...core.schema import NODE_SUMMARY_DTYPE
from ..config import HYBRID_POINT_NAME, OUTPUT_H5
from ..storage.h5_db import (
    TrialKey,
    list_trials,
    open_db,
    read_animal_label,
)


def _decode_trial_state(val: Any) -> str:
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace").strip()
    return str(val or "").strip()


def _run_band_summary_row(g_pt: Any) -> Any | None:
    if "summary" not in g_pt:
        return None
    arr = g_pt["summary"][:]
    if arr.shape[0] == 0:
        return None
    names = arr.dtype.names or ()
    if names and "trial_state" in names:
        for i in range(arr.shape[0]):
            if _decode_trial_state(arr["trial_state"][i]) == "run":
                return arr[i]
        return arr[arr.shape[0] - 1]
    return arr[0]


# Trial-level metrics only (not duplicated from spot_hybrid banded summary rows).
METRIC_MAPPING = {
    "trial_duration_s": "duration_s",
    "n_feedback_error_bouts": "n_incongruent_bouts",
    "feedback_error_duration_s": "incongruent_duration_s",
}



def _is_valid_value(value: Any) -> bool:
    """Check if a value is valid (not None/NaN/Inf)."""
    if value is None:
        return False
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return False
    return True


def _format_value(value: Any) -> str:
    """
    Format a value for CSV output.

    Args:
        value: The value to format (should be valid, not None/NaN)

    Returns:
        Formatted string representation
    """
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        # Format floats with reasonable precision
        return f"{float(value):.6g}"
    return str(value)


def _append_hybrid_summary_metric_rows(
    rows: list[dict[str, Any]],
    base_row: dict[str, Any],
    g_trial: Any,
) -> None:
    g_amb = g_trial.get("ambulation_metrics")
    if g_amb is None or HYBRID_POINT_NAME not in g_amb:
        return
    g_pt = g_amb[HYBRID_POINT_NAME]
    if "summary" not in g_pt:
        return
    arr = g_pt["summary"][:]
    if arr.shape[0] == 0 or not arr.dtype.names or "trial_state" not in arr.dtype.names:
        return
    for i in range(arr.shape[0]):
        band = _decode_trial_state(arr["trial_state"][i])
        for field in NODE_SUMMARY_DTYPE.names:
            raw = arr[field][i]
            if isinstance(raw, np.floating):
                value: Any = float(raw)
            elif isinstance(raw, np.integer):
                value = int(raw)
            else:
                value = raw
            if not _is_valid_value(value):
                continue
            rows.append({
                **base_row,
                "trial_state": band,
                "metric": field,
                "value": _format_value(value),
            })


def _format_session(key: TrialKey) -> str:
    """
    Format session name with appropriate prefix.

    - Habituation phase: H## (e.g., H01, H02)
    - Experimental phase: S## (e.g., S01, S02)
    """
    # Session from database is already like "S01", "S02" etc.
    session_num = key.session.lstrip("SHsh")

    if key.phase == "habituation":
        return f"H{session_num.zfill(2)}"
    else:
        return f"S{session_num.zfill(2)}"


def _extract_trial_metrics(db_path: Path, key: TrialKey) -> dict[str, Any]:
    """
    Extract metric values for a single trial.

    Returns:
        Dictionary with trial metadata and metric values
    """
    result = {
        "duration_s": None,
        "total_distance_m": None,
        "time_immobile_s": None,
        "mean_speed_mps": None,
        "n_movement_bouts": None,
        "latency_to_exit_s": None,
        "time_in_exit_zone_s": None,
        "mean_distance_to_exit_cm": None,
        "path_efficiency": None,
        "time_in_center_s": None,
        "n_center_entries": None,
        "timestamp": "",
        "exit_number": None,
        "n_incongruent_bouts": None,
        "incongruent_duration_s": None,
        "mistrial_reason": "",
        "sleap_model_path": "",
        "trajectory_source": HYBRID_POINT_NAME,
    }

    try:
        with open_db(db_path, "r") as h5:
            g_trial = h5[key.path()]

            # Trial-level attributes: prefer analysis window duration (excludes ITI) for reporting
            result["duration_s"] = g_trial.attrs.get(
                "analysis_duration_s", g_trial.attrs.get("duration_s", None)
            )
            result["timestamp"] = str(g_trial.attrs.get("timestamp", ""))
            result["exit_number"] = g_trial.attrs.get("exit_number", None)
            _mr = g_trial.attrs.get("mistrial_reason", "")
            result["mistrial_reason"] = str(_mr) if _mr else ""
            _smp = g_trial.attrs.get("sleap_model_path", "")
            if isinstance(_smp, bytes):
                _smp = _smp.decode("utf-8", errors="replace")
            result["sleap_model_path"] = str(_smp) if _smp else ""
            _pt = g_trial.attrs.get("primary_trajectory", HYBRID_POINT_NAME)
            if isinstance(_pt, bytes):
                _pt = _pt.decode("utf-8", errors="replace")
            result["trajectory_source"] = str(_pt).strip() or HYBRID_POINT_NAME

            if "ambulation_metrics" in g_trial:
                g_amb = g_trial["ambulation_metrics"]
                if HYBRID_POINT_NAME in g_amb:
                    summary_primary = _run_band_summary_row(g_amb[HYBRID_POINT_NAME])
                    if summary_primary is not None:
                        result["total_distance_m"] = float(summary_primary["total_distance_m"])
                        result["mean_speed_mps"] = float(summary_primary["mean_speed_mps"])
                        result["time_immobile_s"] = float(summary_primary["time_immobile_s"])
                        result["n_movement_bouts"] = int(summary_primary["n_movement_bouts"])
                        result["latency_to_exit_s"] = float(summary_primary["latency_to_exit_s"])
                        result["time_in_exit_zone_s"] = float(summary_primary["time_in_exit_zone_s"])
                        result["mean_distance_to_exit_cm"] = float(
                            summary_primary["mean_distance_to_exit_cm"]
                        )
                        result["path_efficiency"] = float(summary_primary["path_efficiency"])
                        if "time_in_center_s" in summary_primary.dtype.names:
                            result["time_in_center_s"] = float(summary_primary["time_in_center_s"])
                        if "n_center_entries" in summary_primary.dtype.names:
                            result["n_center_entries"] = int(summary_primary["n_center_entries"])

            # Feedback error (incongruent feedback)
            if "feedback" in g_trial:
                g_fb = g_trial["feedback"]
                if "n_incongruent_bouts" in g_fb.attrs:
                    result["n_incongruent_bouts"] = int(g_fb.attrs["n_incongruent_bouts"])
                if "incongruent_duration_s" in g_fb.attrs:
                    result["incongruent_duration_s"] = float(g_fb.attrs["incongruent_duration_s"])

    except Exception as e:
        print(f"  Warning: Error reading {key.path()}: {e}")

    return result


def export_trial_summary(
    db_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    include_mistrials: bool = False,
) -> Path:
    """
    Export trial-level summary metrics to long-format CSV.

    Output columns include trajectory_source, trial_state, metric, value.
    Per-point metrics come from ambulation_metrics/spot_hybrid/summary (iti_wait and run).
    Trial-level metrics use trial_state run.

    Rows are only emitted for metrics that have valid data. Trials without
    processed data (no SLEAP tracking) will not have metric rows in the output.

    Args:
        db_path: Path to VAST database (uses config default if None)
        output_path: Output CSV path (auto-generated if None)
        include_mistrials: If False (default), omit rows for trials with mistrial_reason set.

    Returns:
        Path to generated CSV file
    """
    db_path = db_path or OUTPUT_H5

    if output_path is None:
        output_path = db_path.parent / "exports" / "vast_trial_summary.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    trials = list_trials(db_path)

    # Collect rows in long format
    rows = []

    for key in trials:
        # Extract metrics for this trial
        metrics = _extract_trial_metrics(db_path, key)

        # Exclude mistrials by default (omit all rows for trials with mistrial_reason set)
        if not include_mistrials and (metrics.get("mistrial_reason") or "").strip():
            continue

        # Get animal label for experiment, strain, sex, researcher, drug, treatment
        labels = read_animal_label(db_path, key.animal_id)
        experiment = labels.get("experiment", "")
        strain = labels.get("strain", "")
        sex = labels.get("sex", "")
        researcher = labels.get("researcher", "")
        drug = labels.get("drug", "")
        treatment = labels.get("tx", "")

        # Format session with appropriate prefix
        session = _format_session(key)

        # Prefix trial with 'm' when something went wrong (only when including mistrials)
        trial_str = key.trial
        if include_mistrials and (metrics.get("mistrial_reason") or "").strip():
            trial_str = "m" + trial_str

        # Base info for all metric rows
        exit_num = metrics.get("exit_number")
        base_row = {
            "experiment": experiment,
            "session": session,
            "trial": trial_str,
            "timestamp": metrics["timestamp"],
            "animal_id": key.animal_id,
            "strain": strain,
            "sex": sex,
            "researcher": researcher,
            "drug": drug,
            "treatment": treatment,
            "exit#": _format_value(exit_num) if _is_valid_value(exit_num) else "",
            "sleap_model_path": metrics.get("sleap_model_path") or "",
            "trajectory_source": metrics.get("trajectory_source") or HYBRID_POINT_NAME,
        }

        with open_db(db_path, "r") as h5:
            g_trial = h5[key.path()]
            _append_hybrid_summary_metric_rows(rows, base_row, g_trial)

        # Trial-level metrics (analysis window / feedback); attribute to run band
        for output_metric, db_field in METRIC_MAPPING.items():
            value = metrics.get(db_field)
            if not _is_valid_value(value):
                continue
            rows.append({
                **base_row,
                "trial_state": "run",
                "metric": output_metric,
                "value": _format_value(value),
            })

    # Write CSV
    fieldnames = [
        "experiment", "session", "trial", "timestamp", "animal_id", "strain", "sex",
        "researcher", "drug", "treatment", "exit#", "sleap_model_path", "trajectory_source",
        "trial_state", "metric", "value",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    suffix = " (mistrials excluded)" if not include_mistrials else ""
    print(f"Exported {len(rows)} rows to {output_path}{suffix}")

    return output_path


def export_mistrial_summary(
    db_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Export trials that have a mistrial_reason set (missing data, no tracking, etc.).

    Output CSV columns: animal_id, phase, session, trial, mistrial_reason
    Only includes rows where mistrial_reason is non-empty.
    Prints a short summary (total count and count by reason).
    """
    db_path = db_path or OUTPUT_H5

    if output_path is None:
        output_path = db_path.parent / "exports" / "vast_mistrial_summary.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    trials = list_trials(db_path)
    rows: list[dict[str, str]] = []
    reason_counts: dict[str, int] = {}

    with open_db(db_path, "r") as h5:
        for key in trials:
            try:
                g_trial = h5[key.path()]
                reason = g_trial.attrs.get("mistrial_reason", "")
                if isinstance(reason, bytes):
                    reason = reason.decode("utf-8", errors="replace")
                reason = (reason or "").strip()
                if not reason:
                    continue
                rows.append({
                    "animal_id": key.animal_id,
                    "phase": key.phase,
                    "session": key.session,
                    "trial": key.trial,
                    "mistrial_reason": reason,
                })
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            except Exception:
                continue

    fieldnames = ["animal_id", "phase", "session", "trial", "mistrial_reason"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    n = len(rows)
    if n == 0:
        print("Mistrials: 0 (no trials with mistrial_reason set)")
    else:
        parts = [f"{r}: {c}" for r, c in sorted(reason_counts.items())]
        print(f"Mistrials: {n} total ({', '.join(parts)})")
    print(f"Mistrial list: {output_path}")

    return output_path


def export_all(
    db_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    include_mistrials: bool = False,
) -> dict[str, Path]:
    """
    Export all CSV files.

    Args:
        db_path: Path to VAST database
        output_dir: Directory for output files
        include_mistrials: If True, include mistrial rows in trial summary CSV (default: exclude)

    Returns:
        Dictionary mapping export name to file path
    """
    db_path = db_path or OUTPUT_H5

    if output_dir is None:
        output_dir = db_path.parent / "exports"

    output_dir.mkdir(parents=True, exist_ok=True)

    exports = {}

    # Trial summary (long format); mistrials excluded by default
    exports["trial_summary"] = export_trial_summary(
        db_path,
        output_dir / "vast_trial_summary.csv",
        include_mistrials=include_mistrials,
    )

    # Mistrial summary (trials with mistrial_reason set)
    exports["mistrial_summary"] = export_mistrial_summary(
        db_path,
        output_dir / "vast_mistrial_summary.csv",
    )

    print(f"\nExported {len(exports)} CSV file(s) to {output_dir}")
    return exports


def run_exports_for_db(
    db_path: Path,
    output_dir: Optional[Path] = None,
    include_mistrials: bool = False,
) -> dict[str, Path]:
    """
    Programmatic entry point for running all CSV exports for a single DB.

    Used by the controller GUI to trigger exports directly from the app.
    """
    return export_all(db_path=db_path, output_dir=output_dir, include_mistrials=include_mistrials)


def export_all_for_dbs(
    db_paths: list[Path],
    output_dir: Path,
    include_mistrials: bool = False,
) -> dict[str, Path]:
    """
    Export combined CSVs for multiple databases into a single folder.

    - trial_summary: concatenation of all trial rows from all db_paths
    - mistrial_summary: concatenation of all mistrial rows
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Combined trial summary
    summary_csv = output_dir / "vast_trial_summary.csv"
    all_rows: list[dict[str, Any]] = []
    for db_path in db_paths:
        db_path = Path(db_path)
        trials = list_trials(db_path)
        for key in trials:
            metrics = _extract_trial_metrics(db_path, key)
            if not include_mistrials and (metrics.get("mistrial_reason") or "").strip():
                continue
            labels = read_animal_label(db_path, key.animal_id)
            experiment = labels.get("experiment", "")
            strain = labels.get("strain", "")
            sex = labels.get("sex", "")
            researcher = labels.get("researcher", "")
            drug = labels.get("drug", "")
            treatment = labels.get("tx", "")
            session = _format_session(key)
            trial_str = key.trial
            if include_mistrials and (metrics.get("mistrial_reason") or "").strip():
                trial_str = "m" + trial_str
            exit_num = metrics.get("exit_number")
            base_row = {
                "experiment": experiment,
                "session": session,
                "trial": trial_str,
                "timestamp": metrics["timestamp"],
                "animal_id": key.animal_id,
                "strain": strain,
                "sex": sex,
                "researcher": researcher,
                "drug": drug,
                "treatment": treatment,
                "exit#": _format_value(exit_num) if _is_valid_value(exit_num) else "",
                "sleap_model_path": metrics.get("sleap_model_path") or "",
                "trajectory_source": metrics.get("trajectory_source") or HYBRID_POINT_NAME,
            }
            with open_db(db_path, "r") as h5:
                g_trial = h5[key.path()]
                _append_hybrid_summary_metric_rows(all_rows, base_row, g_trial)
            for output_metric, db_field in METRIC_MAPPING.items():
                value = metrics.get(db_field)
                if not _is_valid_value(value):
                    continue
                all_rows.append({
                    **base_row,
                    "trial_state": "run",
                    "metric": output_metric,
                    "value": _format_value(value),
                })

    fieldnames = [
        "experiment", "session", "trial", "timestamp", "animal_id", "strain", "sex",
        "researcher", "drug", "treatment", "exit#", "sleap_model_path", "trajectory_source",
        "trial_state", "metric", "value",
    ]
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    # Combined mistrial summary
    mistrial_csv = output_dir / "vast_mistrial_summary.csv"
    mistrial_rows: list[dict[str, str]] = []
    with mistrial_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames_m = ["animal_id", "phase", "session", "trial", "mistrial_reason"]
        writer = csv.DictWriter(f, fieldnames=fieldnames_m)
        writer.writeheader()
        for db_path in db_paths:
            db_path = Path(db_path)
            trials = list_trials(db_path)
            with open_db(db_path, "r") as h5:
                for key in trials:
                    try:
                        g_trial = h5[key.path()]
                        reason = g_trial.attrs.get("mistrial_reason", "")
                        if isinstance(reason, bytes):
                            reason = reason.decode("utf-8", errors="replace")
                        reason = (reason or "").strip()
                        if not reason:
                            continue
                        row = {
                            "animal_id": key.animal_id,
                            "phase": key.phase,
                            "session": key.session,
                            "trial": key.trial,
                            "mistrial_reason": reason,
                        }
                        mistrial_rows.append(row)
                        writer.writerow(row)
                    except Exception:
                        continue

    return {
        "trial_summary": summary_csv,
        "mistrial_summary": mistrial_csv,
    }
