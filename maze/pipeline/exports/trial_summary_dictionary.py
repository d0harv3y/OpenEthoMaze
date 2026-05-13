"""
Data dictionary rows for ``trial_summary.csv`` (long-format VAST export).

Outputs tab-separated text suitable for pasting into Excel. Intended to stay in
sync with :mod:`maze.pipeline.exports.csv_trials` while allowing optional
task-specific rows via :func:`register_trial_summary_dictionary_extension` or
optional import of ``maze.pipeline.exports.trial_summary_dictionary_plugins``.
"""

from __future__ import annotations

import csv
import importlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from maze.core.schema import NODE_SUMMARY_DTYPE
from maze.pipeline.db import list_trials, open_db
from maze.pipeline.defaults import HYBRID_POINT_NAME, get_config_snapshot
from maze.pipeline.exports.csv_trials import METRIC_MAPPING
from maze.pipeline.paths import OUTPUT_H5

# ---------------------------------------------------------------------------
# Optional extension hooks (task-specific metrics, extra columns, etc.)
# ---------------------------------------------------------------------------

ExtensionRowsFn = Callable[[Path], Sequence[Mapping[str, str]]]

_extension_row_providers: list[ExtensionRowsFn] = []


def register_trial_summary_dictionary_extension(fn: ExtensionRowsFn) -> ExtensionRowsFn:
    """Register a callable that returns extra dictionary rows for a given results H5 path."""
    _extension_row_providers.append(fn)
    return fn


def _load_optional_plugin_modules() -> None:
    for mod in (
        "maze.pipeline.exports.trial_summary_dictionary_plugins",
        "maze.pipeline.exports.trial_summary_dictionary_tasks",
    ):
        try:
            importlib.import_module(mod)
        except ImportError:
            continue


# Attrs written by :func:`maze.pipeline.db.trial_settings_io.persist_effective_analysis_params`
# plus timing / window fields that define the analyzed segment.
_ANALYSIS_CONTEXT_ATTRS: tuple[str, ...] = (
    "analysis_completed_at",
    "movement_start_threshold_m_per_frame",
    "movement_stop_threshold_m_per_frame",
    "movement_speed_median_window_frames",
    "movement_entry_debounce_frames",
    "movement_exit_debounce_frames",
    "min_movement_bout_duration_frames",
    "movement_inter_bout_interval_frames",
    "max_movement_per_frame_cm",
    "jump_filter_lookahead_frames",
    "filter_frames_no_animal",
    "min_confident_nodes_per_frame",
    "min_node_confidence_threshold",
    "min_valid_frame_run_length",
    "min_mean_confidence_per_frame",
    "trace_interpolate_nans",
    "trace_max_gap_frames",
    "trace_interpolate_low_conf",
    "trace_confidence_threshold",
    "trace_apply_smoothing",
    "trace_smoothing_window",
    "trial_start_frame",
    "seek_to_frame",
    "h5_fps",
    "analysis_duration_s",
    "duration_s",
)

_ANALYSIS_ATTR_LABELS: dict[str, str] = {
    "analysis_completed_at": "analysis_completed_at (UTC)",
    "movement_start_threshold_m_per_frame": "movement start threshold (m per frame)",
    "movement_stop_threshold_m_per_frame": "movement stop threshold (m per frame)",
    "movement_speed_median_window_frames": "movement speed median window (frames)",
    "movement_entry_debounce_frames": "movement entry debounce (frames)",
    "movement_exit_debounce_frames": "movement exit debounce (frames)",
    "min_movement_bout_duration_frames": "min movement bout duration (frames)",
    "movement_inter_bout_interval_frames": "movement inter-bout interval (frames)",
    "max_movement_per_frame_cm": "jump filter max movement per frame (cm)",
    "jump_filter_lookahead_frames": "jump filter lookahead (frames)",
    "filter_frames_no_animal": "filter frames with no confident animal (0/1)",
    "min_confident_nodes_per_frame": "min confident nodes per frame",
    "min_node_confidence_threshold": "min node confidence threshold",
    "min_valid_frame_run_length": "min valid frame run length (frames)",
    "min_mean_confidence_per_frame": "min mean confidence per frame",
    "trace_interpolate_nans": "trace interpolate NaNs (0/1)",
    "trace_max_gap_frames": "trace max gap (frames)",
    "trace_interpolate_low_conf": "trace interpolate low confidence (0/1)",
    "trace_confidence_threshold": "trace confidence threshold",
    "trace_apply_smoothing": "trace apply smoothing (0/1)",
    "trace_smoothing_window": "trace smoothing window (frames)",
    "trial_start_frame": "trial_start_frame (run band starts here in trace rows)",
    "seek_to_frame": "seek_to_frame (absolute video index when present)",
    "h5_fps": "h5_fps (analysis timebase)",
    "analysis_duration_s": "analysis_duration_s (run-window duration written by pipeline)",
    "duration_s": "duration_s (legacy trial duration attr if analysis_duration_s missing)",
}

_TRIAL_SUMMARY_IDENTITY_COLUMNS: tuple[tuple[str, str, str, str], ...] = (
    (
        "experiment",
        "text",
        "",
        "Animal cohort label: experiment (from results DB animal manifest / labels).",
    ),
    (
        "session",
        "text",
        "",
        "Session key formatted for export: H## during habituation phase, S## during experimental phase.",
    ),
    (
        "trial",
        "text",
        "",
        "Trial id within session; prefixed with 'm' when mistrials are included in export.",
    ),
    (
        "timestamp",
        "text",
        "",
        "Trial timestamp string from trial group attrs (acquisition / recording metadata).",
    ),
    (
        "animal_id",
        "text",
        "",
        "Animal identifier (HDF5 path segment under the results file root).",
    ),
    (
        "strain",
        "text",
        "",
        "Strain label from animal manifest when present.",
    ),
    (
        "sex",
        "text",
        "",
        "Sex label from animal manifest when present.",
    ),
    (
        "researcher",
        "text",
        "",
        "Researcher label from animal manifest when present.",
    ),
    (
        "drug",
        "text",
        "",
        "Drug label from animal manifest when present.",
    ),
    (
        "treatment",
        "text",
        "",
        "Treatment label (manifest key ``tx``) from animal manifest when present.",
    ),
    (
        "exit#",
        "text",
        "",
        "Resolved exit index for the trial when available (may be blank).",
    ),
    (
        "sleap_model_path",
        "text",
        "",
        "SLEAP model path recorded for the trial when present.",
    ),
    (
        "trajectory_source",
        "text",
        "",
        f"Primary trajectory / tracking point name (defaults to hybrid key ``{HYBRID_POINT_NAME}``).",
    ),
    (
        "trial_state",
        "text",
        "",
        "Band label for the metric row (e.g. iti_wait vs run) for per-band summaries; "
        "trial-level metrics use run.",
    ),
    (
        "metric",
        "text",
        "",
        "Metric identifier in long format (NODE_SUMMARY field name or mapped trial-level name).",
    ),
    (
        "value",
        "text",
        "",
        "Formatted metric magnitude for this row (numeric values use compact float formatting).",
    ),
)

_NODE_METRIC_HELP: dict[str, str] = {
    "total_distance_m": "Total path length over valid frames in the band (meters).",
    "mean_speed_mps": "Mean speed over valid frames in the band (m/s).",
    "max_speed_mps": "Peak instantaneous speed in the band (m/s).",
    "time_moving_s": "Time classified as moving within the band (seconds).",
    "time_immobile_s": "Time classified as immobile within the band (seconds).",
    "n_movement_bouts": "Count of movement bouts detected in the band.",
    "latency_to_exit_s": "Latency to first exit-zone entry in the band (seconds).",
    "time_in_exit_zone_s": "Time spent inside the exit zone in the band (seconds).",
    "time_in_exit_zone_fraction": "Fraction of band time in the exit zone.",
    "mean_distance_to_exit_cm": "Mean distance to exit hole / zone centerline (cm).",
    "min_distance_to_exit_cm": "Minimum distance to exit (cm).",
    "path_efficiency": "Path efficiency metric (straight-line vs traveled; unitless 0–1 scale).",
    "n_exit_zone_entries": "Number of exit-zone entries in the band.",
    "time_in_center_s": "Time in center zone in the band (seconds).",
    "time_in_center_fraction": "Fraction of band time in the center zone.",
    "n_center_entries": "Number of center-zone entries in the band.",
}

_TRIAL_LEVEL_METRIC_HELP: dict[str, str] = {
    "trial_duration_s": "Analysis window duration (seconds); prefers ``analysis_duration_s`` on the trial group.",
    "n_feedback_error_bouts": "Count of incongruent feedback bouts (from feedback subgroup attrs).",
    "feedback_error_duration_s": "Total duration of incongruent feedback (seconds).",
}


def _decode_attr(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _scalar_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (float, np.floating)):
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return ""
        return f"{v:.12g}"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (str, np.str_)):
        return str(value)
    return str(value)


def _normalize_for_compare(d: Mapping[str, Any]) -> str:
    """Stable JSON for comparing analysis-context dicts across trials."""
    out: dict[str, Any] = {}
    for k in sorted(d.keys()):
        v = d[k]
        if isinstance(v, bytes):
            v = v.decode("utf-8", errors="replace")
        if isinstance(v, (float, np.floating)):
            fv = float(v)
            if math.isnan(fv) or math.isinf(fv):
                out[k] = None
            else:
                out[k] = round(fv, 9)
        elif isinstance(v, (int, np.integer)):
            out[k] = int(v)
        elif isinstance(v, (str, np.str_)):
            out[k] = str(v)
        else:
            out[k] = str(v)
    return json.dumps(out, sort_keys=True, ensure_ascii=False)


def _extract_analysis_context(attrs: Mapping[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for k in _ANALYSIS_CONTEXT_ATTRS:
        if k not in attrs:
            continue
        row[k] = _decode_attr(attrs[k])
    return row


def _analysis_context_for_database(db_path: Path) -> tuple[str, str]:
    """
    Return (reference_trial_path_or_note, formatted_parameter_block).

    If multiple distinct analysis snapshots exist among completed trials, the note
    explains that the parameter block is only one example.
    """
    if not db_path.exists():
        snap = get_config_snapshot()
        parts = [f"{k}={_scalar_to_text(snap[k])}" for k in sorted(snap.keys())]
        block = "; ".join(parts)
        note = (
            f"Database path does not exist ({db_path}). "
            "Parameter list is the pipeline **code default** snapshot (``get_config_snapshot``)."
        )
        return ("(file not found)", f"{note} | {block}")

    trials = list_trials(db_path)
    snapshots: list[tuple[str, dict[str, Any]]] = []
    for key in trials:
        with open_db(db_path, "r") as h5:
            g = h5[key.path()]
            if not g.attrs.get("analysis_completed_at"):
                continue
            snap = _extract_analysis_context(g.attrs)
            if snap:
                snapshots.append((key.path(), snap))

    if not snapshots:
        snap = get_config_snapshot()
        lines = [_scalar_to_text(snap[k]) for k in sorted(snap.keys())]
        pairs = [f"{k}={v}" for k, v in zip(sorted(snap.keys()), lines, strict=True)]
        block = "; ".join(pairs)
        note = (
            "No trial in this file has ``analysis_completed_at`` set. "
            "The parameter list below is the pipeline **code default** snapshot "
            "(``get_config_snapshot``), not a per-trial HDF5 record."
        )
        return ("(no analyzed trials in file)", f"{note} | {block}")

    norms: dict[str, list[str]] = {}
    for path, snap in snapshots:
        n = _normalize_for_compare(snap)
        norms.setdefault(n, []).append(path)

    ref_path, ref_snap = snapshots[0]
    distinct = len(norms)
    header = f"Representative trial HDF5 path: /{ref_path}"
    if distinct > 1:
        header += (
            f" | WARNING: {distinct} distinct analysis-parameter snapshots among "
            f"{len(snapshots)} analyzed trials; expand or script per-trial attrs if needed."
        )

    parts: list[str] = []
    for k in _ANALYSIS_CONTEXT_ATTRS:
        if k not in ref_snap:
            continue
        label = _ANALYSIS_ATTR_LABELS.get(k, k)
        parts.append(f"{label}={_scalar_to_text(ref_snap[k])}")
    return header, " | ".join(parts)


def _metric_units(name: str) -> str:
    if name.endswith("_s"):
        return "s"
    if name.endswith("_mps"):
        return "m/s"
    if name.endswith("_m") and not name.endswith("_cm"):
        return "m"
    if name.endswith("_cm"):
        return "cm"
    if name.endswith("_fraction"):
        return "fraction"
    if name.startswith("n_") or name.endswith("_bouts") or name.endswith("_entries"):
        return "count"
    if name == "path_efficiency":
        return "unitless"
    return ""


def _base_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    rows.append(
        {
            "section": "meta",
            "csv_column": "(document)",
            "metric_name": "",
            "trial_state_scope": "",
            "value_type": "",
            "units": "",
            "description": (
                "trial_summary.csv is long format: each metric is one row. "
                "Identity columns repeat on every row. Rows with mistrial_reason are omitted "
                "unless export is run with include_mistrials=True. "
                f"Per-band metrics are read from ambulation_metrics/{HYBRID_POINT_NAME}/summary "
                "when present. "
                "Representative movement/trace/analysis-window parameters from this HDF5 "
                "(or code defaults if the file is missing / has no completed analysis) "
                "are recorded only on this meta row in analysis_parameters_context."
            ),
            "analysis_parameters_context": "",
        }
    )
    for col, vtype, units, desc in _TRIAL_SUMMARY_IDENTITY_COLUMNS:
        rows.append(
            {
                "section": "identity",
                "csv_column": col,
                "metric_name": "",
                "trial_state_scope": "all rows",
                "value_type": vtype,
                "units": units,
                "description": desc,
                "analysis_parameters_context": "",
            }
        )
    for name in NODE_SUMMARY_DTYPE.names:
        rows.append(
            {
                "section": "long_metric",
                "csv_column": "metric / value",
                "metric_name": str(name),
                "trial_state_scope": "iti_wait and run (separate rows per band when stored)",
                "value_type": "number",
                "units": _metric_units(str(name)),
                "description": _NODE_METRIC_HELP.get(
                    str(name),
                    "Structured summary field from NODE_SUMMARY_DTYPE / banded summary table.",
                ),
                "analysis_parameters_context": "",
            }
        )
    for export_name in METRIC_MAPPING:
        rows.append(
            {
                "section": "trial_level_metric",
                "csv_column": "metric / value",
                "metric_name": export_name,
                "trial_state_scope": "run",
                "value_type": "number",
                "units": _metric_units(export_name),
                "description": _TRIAL_LEVEL_METRIC_HELP.get(
                    export_name,
                    "Trial-level metric mapped in METRIC_MAPPING in csv_trials.py.",
                ),
                "analysis_parameters_context": "",
            }
        )
    return rows


def build_trial_summary_dictionary_rows(db_path: Path | None = None) -> list[dict[str, str]]:
    """
    Build dictionary rows for pasting into Excel (tab-separated export).

    Fills ``analysis_parameters_context`` from the first trial with
    ``analysis_completed_at`` when present; otherwise documents code defaults.
    """
    _load_optional_plugin_modules()
    db_path = Path(db_path or OUTPUT_H5)
    ref_note, param_block = _analysis_context_for_database(db_path)

    rows = _base_rows()
    for r in rows:
        if r["section"] == "meta":
            r["analysis_parameters_context"] = f"{ref_note}. {param_block}"
        else:
            r["analysis_parameters_context"] = ""

    for provider in _extension_row_providers:
        extra = provider(db_path)
        for raw in extra:
            row = {k: str(raw.get(k, "")) for k in _FIELDNAMES}
            if not row.get("analysis_parameters_context"):
                row["analysis_parameters_context"] = ""
            rows.append(row)
    return rows


_FIELDNAMES = (
    "section",
    "csv_column",
    "metric_name",
    "trial_state_scope",
    "value_type",
    "units",
    "description",
    "analysis_parameters_context",
)


def write_trial_summary_dictionary_tsv(
    output_path: Path,
    db_path: Path | None = None,
    *,
    utf8_bom: bool = False,
) -> Path:
    """Write TSV (tab-separated) dictionary for Excel; optional UTF-8 BOM for Excel file open."""
    rows = build_trial_summary_dictionary_rows(db_path=db_path)
    encoding = "utf-8-sig" if utf8_bom else "utf-8"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding=encoding) as f:
        w = csv.DictWriter(f, fieldnames=list(_FIELDNAMES), delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Generate trial_summary.csv data dictionary (TSV for Excel)."
    )
    p.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"Results HDF5 used to read analysis attrs (default: {OUTPUT_H5})",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output .tsv path (default: <db parent>/exports/trial_summary_data_dictionary.tsv)",
    )
    p.add_argument(
        "--utf8-bom",
        action="store_true",
        help="Write UTF-8 BOM (useful when opening the file directly in Excel on Windows).",
    )
    args = p.parse_args(list(argv) if argv is not None else None)

    db_path = args.db or OUTPUT_H5
    if args.output is None:
        out = Path(db_path).parent / "exports" / "trial_summary_data_dictionary.tsv"
    else:
        out = Path(args.output)

    if not Path(db_path).exists():
        print(f"Warning: database not found at {db_path}; analysis context will use code defaults.")
    written = write_trial_summary_dictionary_tsv(out, db_path=db_path, utf8_bom=args.utf8_bom)
    print(f"Wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
