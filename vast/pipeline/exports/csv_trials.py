from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import csv
import math
import numpy as np

from ..config import IN_RANGE_POINT_NAME, OUTPUT_H5
from ..storage.h5_db import (
    TrialKey,
    list_trials,
    open_db,
    read_animal_label,
)


def _iter_trial_keys(db_path: Path) -> Iterable[TrialKey]:
    """Yield all trials in the database."""
    return list_trials(db_path)


def _read_node_summaries_by_state(g_trial, point_name: str) -> np.ndarray | None:
    """Read banded node summaries (summary_by_state) if present."""
    g_amb = g_trial.get("ambulation_metrics")
    if g_amb is None or point_name not in g_amb:
        return None
    g_pt = g_amb[point_name]
    if "summary_by_state" in g_pt:
        return g_pt["summary_by_state"][:]
    return None


def _read_node_summary(g_trial, point_name: str) -> np.ndarray | None:
    """Read legacy single summary dataset for a tracking point."""
    g_amb = g_trial.get("ambulation_metrics")
    if g_amb is None or point_name not in g_amb:
        return None
    g_pt = g_amb[point_name]
    if "summary" in g_pt:
        return g_pt["summary"][:]
    return None


def _rows_for_trial(
    db_path: Path,
    key: TrialKey,
    include_mistrials: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open_db(db_path, "r") as h5:
        g_trial = h5[key.path()]

        # Skip mistrials unless explicitly requested.
        mistrial_reason = g_trial.attrs.get("mistrial_reason", "")
        if isinstance(mistrial_reason, bytes):
            mistrial_reason = mistrial_reason.decode("utf-8")
        if mistrial_reason and not include_mistrials:
            return []

        primary_trajectory = g_trial.attrs.get("primary_trajectory", "spot")
        if isinstance(primary_trajectory, bytes):
            primary_trajectory = primary_trajectory.decode("utf-8")

        # Prefer banded summaries; fall back to single-summary when not available.
        spot_banded = _read_node_summaries_by_state(g_trial, "spot")
        inrange_banded = _read_node_summaries_by_state(g_trial, IN_RANGE_POINT_NAME)

        if spot_banded is not None and inrange_banded is not None:
            # Expect rows for iti_wait and run bands; build CSV rows for each band.
            for band in ["iti_wait", "run"]:
                band_bytes = band.encode("utf-8")
                spot_rows = spot_banded[spot_banded["trial_state"] == band_bytes]
                inrange_rows = inrange_banded[inrange_banded["trial_state"] == band_bytes]
                if not len(spot_rows) or not len(inrange_rows):
                    continue
                spot_summary = spot_rows[0]
                inrange_summary = inrange_rows[0]
                # Primary metrics for this band (use primary_trajectory to pick source).
                primary = spot_summary if primary_trajectory == "spot" else inrange_summary
                # Core primary metric: total_distance_m
                rows.append({
                    "animal_id": key.animal_id,
                    "session": key.session,
                    "trial": key.trial,
                    "trial_state": band,
                    "primary_trajectory": primary_trajectory,
                    "metric": "total_distance_m",
                    "value": float(primary["total_distance_m"]),
                })
                # Per-trajectory extras for this band.
                rows.append({
                    "animal_id": key.animal_id,
                    "session": key.session,
                    "trial": key.trial,
                    "trial_state": band,
                    "primary_trajectory": primary_trajectory,
                    "metric": "spot_total_distance_m",
                    "value": float(spot_summary["total_distance_m"]),
                })
                rows.append({
                    "animal_id": key.animal_id,
                    "session": key.session,
                    "trial": key.trial,
                    "trial_state": band,
                    "primary_trajectory": primary_trajectory,
                    "metric": f"{IN_RANGE_POINT_NAME}_total_distance_m",
                    "value": float(inrange_summary["total_distance_m"]),
                })
                rows.append({
                    "animal_id": key.animal_id,
                    "session": key.session,
                    "trial": key.trial,
                    "trial_state": band,
                    "primary_trajectory": primary_trajectory,
                    "metric": "spot_latency_to_exit_s",
                    "value": float(spot_summary["latency_to_exit_s"]),
                })
                rows.append({
                    "animal_id": key.animal_id,
                    "session": key.session,
                    "trial": key.trial,
                    "trial_state": band,
                    "primary_trajectory": primary_trajectory,
                    "metric": f"{IN_RANGE_POINT_NAME}_latency_to_exit_s",
                    "value": float(inrange_summary["latency_to_exit_s"]),
                })
        else:
            # Legacy path: single band (treated as run) without trial_state split.
            spot_summary_arr = _read_node_summary(g_trial, "spot")
            inrange_summary_arr = _read_node_summary(g_trial, IN_RANGE_POINT_NAME)
            if spot_summary_arr is None or inrange_summary_arr is None:
                return []
            spot_summary = spot_summary_arr[0]
            inrange_summary = inrange_summary_arr[0]
            band = "run"
            primary = spot_summary if primary_trajectory == "spot" else inrange_summary
            rows.append({
                "animal_id": key.animal_id,
                "session": key.session,
                "trial": key.trial,
                "trial_state": band,
                "primary_trajectory": primary_trajectory,
                "metric": "total_distance_m",
                "value": float(primary["total_distance_m"]),
            })
            rows.append({
                "animal_id": key.animal_id,
                "session": key.session,
                "trial": key.trial,
                "trial_state": band,
                "primary_trajectory": primary_trajectory,
                "metric": "spot_total_distance_m",
                "value": float(spot_summary["total_distance_m"]),
            })
            rows.append({
                "animal_id": key.animal_id,
                "session": key.session,
                "trial": key.trial,
                "trial_state": band,
                "primary_trajectory": primary_trajectory,
                "metric": f"{IN_RANGE_POINT_NAME}_total_distance_m",
                "value": float(inrange_summary["total_distance_m"]),
            })
            rows.append({
                "animal_id": key.animal_id,
                "session": key.session,
                "trial": key.trial,
                "trial_state": band,
                "primary_trajectory": primary_trajectory,
                "metric": "spot_latency_to_exit_s",
                "value": float(spot_summary["latency_to_exit_s"]),
            })
            rows.append({
                "animal_id": key.animal_id,
                "session": key.session,
                "trial": key.trial,
                "trial_state": band,
                "primary_trajectory": primary_trajectory,
                "metric": f"{IN_RANGE_POINT_NAME}_latency_to_exit_s",
                "value": float(inrange_summary["latency_to_exit_s"]),
            })
    return rows


def export_trial_summary(
    db_path: Path,
    output_path: Path,
    include_mistrials: bool = False,
) -> None:
    """
    Export per-trial summary metrics to a CSV file.

    Emits one logical row per (trial, trial_state_band, metric), where
    trial_state_band is \"iti_wait\" or \"run\" when banded summaries are available.
    """
    db_path = Path(db_path)
    output_path = Path(output_path)
    all_rows: list[dict[str, Any]] = []
    for key in _iter_trial_keys(db_path):
        all_rows.extend(_rows_for_trial(db_path, key, include_mistrials=include_mistrials))
    if not all_rows:
        # Still write header for empty export.
        fieldnames = ["animal_id", "session", "trial", "trial_state", "primary_trajectory", "metric", "value"]
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        return

    fieldnames = ["animal_id", "session", "trial", "trial_state", "primary_trajectory", "metric", "value"]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)


def export_all(
    db_path: Path,
    output_dir: Path | None = None,
    include_mistrials: bool = False,
) -> Dict[str, Path]:
    """
    Export all standard CSV outputs.

    Currently only trial summary CSV is implemented.
    """
    db_path = Path(db_path)
    if output_dir is None:
        output_dir = db_path.parent
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_csv = output_dir / "vast_trial_summary.csv"
    export_trial_summary(db_path=db_path, output_path=summary_csv, include_mistrials=include_mistrials)
    return {"trial_summary": summary_csv}

"""
CSV export module for VAST pipeline.

Exports trial metrics to a long-format CSV file for downstream analysis.
Output format:
    experiment, session, trial, timestamp, animal_id, strain, sex, researcher, drug, treatment, exit#, metric, value

Metrics exported:
    - trial_duration_s, total_distance_m, time_still_s, avg_speed_mps, n_movement_bout
    - latency_to_exit_s, time_in_exit_zone_s, mean_distance_to_exit_cm, path_efficiency
    - time_in_center_s, n_center_entries (center zone with 0.5s debounce)
    - n_feedback_error_bouts, feedback_error_duration_s (stimuli incongruencies)
"""

# Mapping of metric names from database to output CSV (primary = from primary_trajectory attr)
METRIC_MAPPING = {
    "trial_duration_s": "duration_s",  # database attr name
    "total_distance_m": "total_distance_m",
    "time_still_s": "time_immobile_s",
    "avg_speed_mps": "mean_speed_mps",
    "n_movement_bout": "n_movement_bouts",
    "latency_to_exit_s": "latency_to_exit_s",
    "time_in_exit_zone_s": "time_in_exit_zone_s",
    "mean_distance_to_exit_cm": "mean_distance_to_exit_cm",
    "path_efficiency": "path_efficiency",
    "time_in_center_s": "time_in_center_s",
    "n_center_entries": "n_center_entries",
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
        "primary_trajectory": "spot",
        "spot_total_distance_m": None,
        "spot_latency_to_exit_s": None,
        "in_range_total_distance_m": None,
        "in_range_latency_to_exit_s": None,
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
            _pt = g_trial.attrs.get("primary_trajectory", "spot")
            if isinstance(_pt, bytes):
                _pt = _pt.decode("utf-8", errors="replace")
            result["primary_trajectory"] = str(_pt).strip() or "spot"

            # Ambulation + exit: read spot and in-range summaries; primary metrics from primary_trajectory
            def _read_summary(g_amb: Any, point_name: str) -> Optional[Any]:
                if point_name not in g_amb or "summary" not in g_amb[point_name]:
                    return None
                return g_amb[point_name]["summary"][0]

            if "ambulation_metrics" in g_trial:
                g_amb = g_trial["ambulation_metrics"]
                summary_spot = _read_summary(g_amb, "spot")
                summary_inrange = _read_summary(g_amb, "in-range")
                primary = result["primary_trajectory"]
                summary_primary = summary_inrange if primary == "in-range" else summary_spot
                if summary_primary is None:
                    summary_primary = summary_spot or summary_inrange
                if summary_primary is not None:
                    result["total_distance_m"] = float(summary_primary["total_distance_m"])
                    result["mean_speed_mps"] = float(summary_primary["mean_speed_mps"])
                    result["time_immobile_s"] = float(summary_primary["time_immobile_s"])
                    result["n_movement_bouts"] = int(summary_primary["n_movement_bouts"])
                    result["latency_to_exit_s"] = float(summary_primary["latency_to_exit_s"])
                    result["time_in_exit_zone_s"] = float(summary_primary["time_in_exit_zone_s"])
                    result["mean_distance_to_exit_cm"] = float(summary_primary["mean_distance_to_exit_cm"])
                    result["path_efficiency"] = float(summary_primary["path_efficiency"])
                    if "time_in_center_s" in summary_primary.dtype.names:
                        result["time_in_center_s"] = float(summary_primary["time_in_center_s"])
                    if "n_center_entries" in summary_primary.dtype.names:
                        result["n_center_entries"] = int(summary_primary["n_center_entries"])
                if summary_spot is not None:
                    result["spot_total_distance_m"] = float(summary_spot["total_distance_m"])
                    result["spot_latency_to_exit_s"] = float(summary_spot["latency_to_exit_s"])
                if summary_inrange is not None:
                    result["in_range_total_distance_m"] = float(summary_inrange["total_distance_m"])
                    result["in_range_latency_to_exit_s"] = float(summary_inrange["latency_to_exit_s"])

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

    Output columns:
        experiment, session, trial, timestamp, animal_id, strain, sex, researcher, drug, treatment, exit#, metric, value

    Metrics exported:
        trial_duration_s, total_distance_m, time_still_s, avg_speed_mps, n_movement_bout

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
            "primary_trajectory": metrics.get("primary_trajectory") or "spot",
        }

        # Create one row per metric (long format), skip if no valid value
        for output_metric, db_field in METRIC_MAPPING.items():
            value = metrics.get(db_field)
            if not _is_valid_value(value):
                continue  # Skip rows with no data
            rows.append({
                **base_row,
                "metric": output_metric,
                "value": _format_value(value),
            })

        # Expose both trajectories (spot and in-range) for key metrics
        for metric_key, output_name in (
            ("spot_total_distance_m", "spot_total_distance_m"),
            ("spot_latency_to_exit_s", "spot_latency_to_exit_s"),
            ("in_range_total_distance_m", "in_range_total_distance_m"),
            ("in_range_latency_to_exit_s", "in_range_latency_to_exit_s"),
        ):
            value = metrics.get(metric_key)
            if _is_valid_value(value):
                rows.append({
                    **base_row,
                    "metric": output_name,
                    "value": _format_value(value),
                })

    # Write CSV
    fieldnames = [
        "experiment", "session", "trial", "timestamp", "animal_id", "strain", "sex",
        "researcher", "drug", "treatment", "exit#", "sleap_model_path", "primary_trajectory",
        "metric", "value",
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
                "primary_trajectory": metrics.get("primary_trajectory") or "spot",
            }
            for output_metric, db_field in METRIC_MAPPING.items():
                value = metrics.get(db_field)
                if not _is_valid_value(value):
                    continue
                all_rows.append({
                    **base_row,
                    "metric": output_metric,
                    "value": _format_value(value),
                })
            for metric_key, output_name in (
                ("spot_total_distance_m", "spot_total_distance_m"),
                ("spot_latency_to_exit_s", "spot_latency_to_exit_s"),
                ("in_range_total_distance_m", "in_range_total_distance_m"),
                ("in_range_latency_to_exit_s", "in_range_latency_to_exit_s"),
            ):
                value = metrics.get(metric_key)
                if _is_valid_value(value):
                    all_rows.append({
                        **base_row,
                        "metric": output_name,
                        "value": _format_value(value),
                    })

    fieldnames = [
        "experiment", "session", "trial", "timestamp", "animal_id", "strain", "sex",
        "researcher", "drug", "treatment", "exit#", "sleap_model_path", "primary_trajectory",
        "metric", "value",
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
