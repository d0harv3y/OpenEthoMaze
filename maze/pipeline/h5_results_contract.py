"""
H5 results layout: generic vs task-specific analysis products.

**Generic (shared trial group)**
Per-point XY tables under the trial group, ambulation metrics, movement bouts,
banded node summaries (ITI vs run), feedback error summaries, mistrial attrs,
analysis duration, optional QC images. Analysis **parameters** (movement bouts,
jump filter, trace interpolation, confidence gates) are persisted only after a
successful :func:`maze.pipeline.process_trial.process_trial` run via
:func:`maze.pipeline.db.trial_settings_io.persist_effective_analysis_params`,
including ``analysis_completed_at`` (UTC ISO-8601).

**Task-specific**
e.g. radial-arm geometry and exit resolution under ``task_data/radial_arm/``,
extra attrs via ``write_trial_attrs`` for task metrics.

**Acquisition vs pipeline**
Live acquisition writes geometry/session attrs via ``write_trial_settings`` /
RAM equivalents **without** pre-stamping analysis parameters; the offline
pipeline merges GUI :class:`~maze.controller.acquisition.shared_config.AnalysisTrajectoryConfig`
and :class:`~maze.controller.acquisition.shared_config.AnalysisTraceQualityConfig`
when requested, then persists the effective set after analysis.

**``write_config_params``**
Global defaults snapshot for reproducibility; not a per-trial analysis profile.
Per-trial provenance is the attr set written by ``persist_effective_analysis_params``.

**Export**
Long-format CSV (``csv_trials``) is VAST-first; RAM-shaped trials in the same H5
may need schema review before enabling combined export.

**Tracking (planned v2)**
Controller-first kpMS and E6 multi-stream ethograms need dense pose and blob
polygons in-trial, not only ``sleap_path`` sidecars. Target layout:
``docs/h5_tracking_contract.md`` (``tracking/anatomical``, ``tracking/blob``).
"""
