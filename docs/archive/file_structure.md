## VAST controller trial file structure (HDF5)

This documents the on-disk layout produced by `vast_controller` so that `vast_pipeline`
and other tools can consume it consistently.

All paths below are relative to the HDF5 root.

- **Trial group**: `/{animal_id}/{session_id}/{trial}`
  - Attributes:
    - `arena_radius_px` (float)
    - `px_per_cm` (float)
    - `arena_center_x_px` (float)
    - `arena_center_y_px` (float)
    - `timestamp` (ISO 8601, optional)
    - `phase` (`"habituation" | "habituation_training" | "VAST"`)
    - `run_mode` (`"continuous" | "alternating"`)
    - `exit_x`, `exit_y` (float, pixels)
    - `trial_start_frame` (int, usually 0)
    - `fps` (float, per-frame frame rate)
    - `n_frames` (int, number of recorded frames)
    - `duration_s` (float, duration of recording in seconds)

- **Ambulation metrics (per-frame XY table)**:
  - Group: `/ {animal_id}/{session_id}/{trial}/ambulation_metrics/spot`
    - Dataset: `xy` with dtype:
      - `frame_index` (`uint32`)
      - `t_s` (`float64`) – time since start of recording (seconds)
      - `x`, `y` (`float32`) – position in pixels
      - `dist_to_exit_px` (`float32`) – distance to exit center in pixels
      - `trial_state` (`S10`) – `"iti" | "wait" | "run"`
      - `in_exit_zone` (`uint8`) – 1 if inside exit zone, else 0
      - `valid` (`uint8`) – 1 if tracking is valid, else 0
      - `is_moving` (`uint8`) – reserved; currently 0/1
    - Attribute: `fps` (float, same as trial-level `fps`)

- **Unified feedback table (per-frame)**:
  - Group: `/ {animal_id}/{session_id}/{trial}/feedback`
    - Dataset: `table` with dtype:
      - `frame_index` (`uint32`) – global frame index for the trial
      - `trial_state` (`S16`) – `"iti" | "wait" | "run"` (string-encoded state)
      - `motor_fb` (`float32`) – motor feedback level; currently the duty cycle (%)
      - `light_fb` (`float32`) – reserved for light feedback (0.0 when unused)
      - `sound_fb` (`float32`) – reserved for sound feedback (0.0 when unused)

`vast_pipeline` should:

- Use `feedback/table` as the single source of feedback signals, keyed by `frame_index`.
- Join `ambulation_metrics/spot/xy` and `/feedback/table` on `frame_index`.
- Treat all spatial quantities (`x`, `y`, `dist_to_exit_px`, `exit_x`, `exit_y`) as **pixels**;
  conversions to centimeters should be done on the pipeline side using `px_per_cm`.

