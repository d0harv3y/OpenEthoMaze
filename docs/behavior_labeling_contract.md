# Behavior labeling artifact contract (S0)

The producer-agnostic artifact every Behavior **producer** (A/B/D) emits and the evaluation harness reads. This *is* the producer seam (ADR-0004). Implementation: [`maze/kpms/behavior_ethogram/labeling.py`](../maze/kpms/behavior_ethogram/labeling.py). Schema id: `behavior_labeling_v1`.

## Location

```
<kpms_root>/behavior_ethogram/producers/<producer>/<fit_id>/
  ├── behavior_frames.h5      # canonical per-frame labels (source-video timeline)
  ├── behavior_bouts.csv      # derived RLE export (do not treat as canonical)
  └── provenance.json
```

Path helpers: `maze.kpms.behavior_ethogram.paths.producer_dir(kpms_root, producer, fit_id)` and `behavior_frames_h5(dir)` / `behavior_bouts_csv(dir)` / `behavior_provenance_json(dir)`.

## `behavior_frames.h5` (canonical)

Root attrs: `schema` (`behavior_labeling_v1`), `producer` (str), `fit_id` (str), `fps` (float).

```
/trials/t000000, t000001, …          # one group per trial, index-named, ordered
    attrs: trial_key (str)           # real key; index naming avoids HDF5 charset issues
    source_frame_index : int64 (T,)  # index into the ORIGINAL video/SLEAP timeline; STRICTLY INCREASING; may have gaps
    behavior_id        : int32 (T,)  # -1 (UNLABELED) = gap / producer left unlabeled
```

**Invariants** (enforced in `TrialFrameLabels.__post_init__`): `len(source_frame_index) == len(behavior_id)`; `source_frame_index` strictly increasing. The id→name map lives in `provenance.json`, not the H5.

## `behavior_bouts.csv` (derived)

Run-length encoding of the per-frame stream (`labeling_to_bouts`); regenerable, **not** authoritative. Unlabeled runs are dropped by default. Columns:

| Column | Type | Notes |
|---|---|---|
| `trial_key` | str | |
| `behavior_id` | int | |
| `behavior_name` | str | from provenance map; "" if unnamed |
| `bout_index` | int | contiguous per trial (gaps from dropped unlabeled runs are not counted) |
| `start_frame` | int | **source** frame index of first row in run |
| `end_frame` | int | **source** frame index of last row in run (inclusive) |
| `n_frames` | int | count of labeled rows (not `end-start+1`, since source frames may have gaps) |
| `duration_s` | float | `n_frames / fps` |

## `provenance.json`

```json
{
  "schema": "behavior_labeling_v1",
  "producer": "dummy", "fit_id": "seed_042", "fps": 20.0,
  "created_at": "<ISO-8601 UTC>",
  "n_trials": 2, "n_labeled_frames": 10,
  "behavior_names": {"0": "pause", "2": "locomote"},
  "behavior_anchor_buckets": {"0": "still", "2": "moving"},
  "params": { "...": "producer hyperparams" },
  "input_hashes": { "results_apply.h5": "<sha256>" }
}
```

Producers should populate `input_hashes` (e.g. via `labeling.hash_file`) and `params` for reproducibility. Optional `behavior_anchor_buckets` maps behavior id → `moving` | `still` | `ignore` for harness scoring (S3.1 grammar export).

## Consumer rules

- Read via `read_behavior_labeling(dir)`; treat `behavior_frames.h5` as canonical and the CSV as a convenience export.
- Join to anchors / held-out kinematics on `(trial_key, source_frame_index)`.
- Never import a producer module to introspect its internals (ADR-0004).
