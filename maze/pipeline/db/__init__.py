"""
Public result-database API for the maze pipeline.

The focused implementation remains split across narrower modules so task-specific
extensions can land without rebuilding another monolithic facade.
"""

from __future__ import annotations

from ._shared import open_db
from .ambulation_bouts import movement_bout_dtype, write_movement_bouts
from .ambulation_summary import (
    _summary_run_row,
    ambulation_summary_dtype,
    exit_metrics_dtype,
    node_summary_by_state_dtype,
    node_summary_dtype,
    read_exit_metrics,
    write_node_summary_by_state,
)
from .ambulation_xy import read_xy_table, write_xy_table, xy_table_dtype
from .cohort_manifest import (
    read_animal_label,
    upsert_trial_manifest_row,
    write_animal_label,
    write_trial_manifest_rows,
)
from .feedback import (
    read_feedback_series,
    write_feedback_error_summary,
    write_feedback_series,
)
from .metadata import init_database, read_arena_type
from .qc_image_store import read_qc_image, write_qc_image
from .trial_attributes import (
    read_task_group_attrs,
    write_analysis_duration,
    write_animal_notes_attr,
    write_config_params,
    write_mistrial_reason,
    write_primary_trajectory,
    write_sleap_model_path,
    write_sleap_path,
    write_task_group_attrs,
    write_trial_attrs,
    write_trial_frame_counts,
    write_video_meta,
)
from .trial_groups import (
    delete_animal_group,
    delete_trial_group,
    ensure_trial_group,
    list_trials,
    read_trial_meta_for_manifest,
    trial_has_settings,
)
from .trial_key import (
    TrialKey,
    ram_sessions_equivalent,
    ram_trials_equivalent,
    resolve_trial_key_for_hdf5,
)
from .trial_settings_io import (
    read_radial_arm_trial_settings,
    read_trial_settings,
    write_radial_arm_trial_settings,
    write_trial_settings,
)

__all__ = [
    "TrialKey",
    "ram_sessions_equivalent",
    "ram_trials_equivalent",
    "resolve_trial_key_for_hdf5",
    "open_db",
    "init_database",
    "read_arena_type",
    "write_trial_attrs",
    "write_task_group_attrs",
    "read_task_group_attrs",
    "ensure_trial_group",
    "write_trial_settings",
    "read_trial_settings",
    "write_radial_arm_trial_settings",
    "read_radial_arm_trial_settings",
    "write_feedback_series",
    "read_feedback_series",
    "write_feedback_error_summary",
    "read_trial_meta_for_manifest",
    "write_trial_frame_counts",
    "write_video_meta",
    "write_analysis_duration",
    "write_primary_trajectory",
    "write_mistrial_reason",
    "write_sleap_path",
    "write_sleap_model_path",
    "xy_table_dtype",
    "write_xy_table",
    "read_xy_table",
    "movement_bout_dtype",
    "write_movement_bouts",
    "node_summary_dtype",
    "node_summary_by_state_dtype",
    "write_node_summary_by_state",
    "_summary_run_row",
    "read_exit_metrics",
    "exit_metrics_dtype",
    "ambulation_summary_dtype",
    "write_qc_image",
    "read_qc_image",
    "write_animal_notes_attr",
    "upsert_trial_manifest_row",
    "write_trial_manifest_rows",
    "write_animal_label",
    "read_animal_label",
    "trial_has_settings",
    "delete_trial_group",
    "delete_animal_group",
    "list_trials",
    "write_config_params",
]
