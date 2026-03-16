## Trial-state bands in VAST pipeline

The VAST pipeline now splits within-trial analysis into two bands based on frame
position relative to the trial start frame:

- **iti_wait**: frames before `trial_start_frame` (ITI + wait-to-start portion).
- **run**: frames from `trial_start_frame` onward (main trial portion).

### HDF5 outputs

For each trial at path `/{animal_id}/{session}/{trial}` in the results HDF5
(`vast_results.h5`):

- **Per-point banded summaries**:
  - Group: `/ {animal_id}/{session}/{trial}/ambulation_metrics/<point_name>`
  - Dataset: `summary_by_state` with dtype:
    - `trial_state` (`S16`): `"iti_wait"` or `"run"`.
    - All fields from `node_summary_dtype`:
      - `total_distance_m`, `mean_speed_mps`, `max_speed_mps`
      - `time_moving_s`, `time_immobile_s`, `n_movement_bouts`
      - `latency_to_exit_s`, `time_in_exit_zone_s`, `time_in_exit_zone_fraction`
      - `mean_distance_to_exit_cm`, `min_distance_to_exit_cm`
      - `path_efficiency`, `n_exit_zone_entries`
      - `time_in_center_s`, `time_in_center_fraction`, `n_center_entries`
  - The legacy `summary` dataset remains and corresponds to the **run** band for
    backwards compatibility.

- **QC images**:
  - Group: `/ {animal_id}/{session}/{trial}/qc_images`
  - Datasets:
    - `composite_iti_wait`: composite QC image (dwell heatmap + trajectory) for the
      ITI/WAIT band.
    - `composite_run`: composite QC image for the RUN band.
  - Existing tools that expect only `composite` should be updated to look for the
    banded images instead.

### CSV export

The trial summary CSV produced by `vast_pipeline.exports.csv_exporter.export_trial_summary`
now includes a `trial_state` column and emits separate rows per band:

- Columns:
  - `animal_id`, `session`, `trial`
  - `trial_state` (`"iti_wait"` or `"run"`)
  - `primary_trajectory` (`"spot"` or `"in-range"`)
  - `metric` (e.g. `total_distance_m`, `spot_total_distance_m`,
    `in-range_total_distance_m`, `spot_latency_to_exit_s`,
    `in-range_latency_to_exit_s`)
  - `value` (float)

For each trial and band, primary metrics are taken from the summary for the
`primary_trajectory`, and per-trajectory metrics are exported for both `spot`
and `in-range` where available.

