# Phase T agent prompt (copy into a new Cursor chat)

Use for **Tracking v2 + multi-stream kpMS** slices from [tracking_kpms_master_plan.md](tracking_kpms_master_plan.md).

**Rules for every slice**

- One PR / one agent session = **one slice ID** only (e.g. T1b, not T1b+T1c).
- Read [h5_tracking_contract.md](h5_tracking_contract.md) before editing schema or I/O.
- `uv run pytest tests/ -q` green before and after; no GPU required unless slice says W1.
- Do not change fit hyperparameters unless slice T4c says so.
- Windows paths only in `paths_local.py` (gitignored), never in `maze/` defaults.

---

## Prompt — T0 schema + tracking I/O

```
Scope: T0 only (docs/tracking_kpms_master_plan.md).

Implement tracking v2 schema constants and pure HDF5 I/O — no acquisition or kpMS wiring yet.

Deliverables:
- maze/pipeline/tracking_io.py (or maze/core/tracking_io.py): write/read tracking/anatomical and tracking/blob groups per h5_tracking_contract.md
- Schema version bump helper: controller_schema_version v2 when tracking/ present
- maze/core/anatomy.py: use existing BLOB_VERTEX_COUNT / BLOB_NODE_NAMES (do not change count)
- tests/test_tracking_io.py: round-trip anatomical + blob on synthetic trial group in tmp_path

Out of scope: TrialRecorder, build_kpms_inputs, GUI, WSL.

Acceptance: uv run pytest tests/test_tracking_io.py -q passes; no new lab drive defaults.
```

---

## Prompt — T1a anatomical I/O only

```
Scope: T1a only. Prerequisite: T0 merged.

Wire anatomical write/read into acquisition-facing API only — no TrialRecorder yet.

Deliverables:
- Public functions: append or flush anatomical frames (frame_index, x, y, score, valid) + attrs pose_source, fps, node_names
- Unit test calling flush on empty trial group

Out of scope: camera_loop, blob, kpMS.

Acceptance: pytest green; functions documented in tracking_io module docstring.
```

---

## Prompt — T1b acquisition anatomical flush

```
Scope: T1b only. Prerequisites: T0, T1a.

Persist live SLEAP pose from acquisition into tracking/anatomical at trial stop.

Touch:
- maze/controller/acquisition/recording.py (TrialRecorder buffers)
- maze/controller/acquisition/gui/camera_loop.py (pass pose_xy, scores, valid each tick)
- pose_source=sleap_live; jump filter policy same as display path

Out of scope: blob polygon, process_trial backfill, kpMS.

Acceptance: uv run pytest tests/ -q; optional manual note in PR that smoke maze-daq records tracking/anatomical on one trial.
```

---

## Prompt — T1c blob orientation + 8-gon

```
Scope: T1c only. Prerequisite: T0. **Shipped.**

Pure library: contour (or mask) → 8 vertices in motion-consistent order.

Deliverables:
- maze/pipeline/blob_orient.py: resample to BLOB_VERTEX_COUNT, heading from centroid velocity, temporal unwrap, confidence when speed < epsilon
- Optional: use neck→nose from anatomical frame as heading hint when both valid (document in docstring)
- tests/test_blob_orient.py: synthetic ellipse + known velocity → stable vertex order

Out of scope: H5 write, kpMS. Live acquisition wiring is T1d (`TrackingController.orient_blob`).

Acceptance: pytest on synthetic cases; no cv2 import in kpms/.
```

---

## Prompt — T1d acquisition blob flush

```
Scope: T1d only. Prerequisites: T0, T1c. **Shipped** (polygon-first, Jun 2026).

Persist tracking/blob at trial stop from oriented backup polygon (no mask round-trip).

Touch (as implemented):
- maze/controller/acquisition/tracking.py: fallback returns blob_contour; TrackingController.orient_blob() owns BlobOrientTracker state
- maze/controller/acquisition/gui/camera_loop.py: crop offset → full-image xy; same polygon for overlay (fillPoly) and recorder
- maze/controller/acquisition/recording.py: BlobTrackingBuffer from precomputed blob_xy, valid, heading_rad, score
- blob_source=backup_live; backup_params_json from fallback settings

Out of scope: kpMS stream B (T4a), offline re-track, virtual acq blob materialization.

Acceptance: tests/controller/test_recording_blob.py, test_tracking_blob_fallback.py, test_blob_polygon_overlay.py; tracking/blob round-trip via test_tracking_io.
```

---

## Prompt — T2a canonical H5 resolver + load anatomical

```
Scope: T2a only. Prerequisites: T0.

Implement manifest-aware canonical trial HDF5 resolution per h5_tracking_contract.md § Canonical file.

Deliverables:
- maze/kpms/h5_pose.py (or maze/pipeline/tracking_read.py): resolve_canonical_trial_h5(manifest, db_path) → Path
- load_anatomical_from_h5(path, trial_key) → arrays + attrs for kpMS preprocess

Out of scope: build_kpms_inputs changes, blob stream.

Acceptance: tests with tmp H5 + TrialManifest rows; v1 files without tracking/ return None gracefully.
```

---

## Prompt — T2b build_kpms_inputs H5-first (stream A)

```
Scope: T2b only. Prerequisites: T2a.

Change anatomical kpMS preprocess to prefer trial H5 over sleap_path.

Touch:
- maze/kpms/preprocess.py: read order H5 anatomical → sleap sidecar → skip missing_pose
- maze/kpms/manifest_subset.py: require_sleap=False when manifest row has resolvable H5 pose (helper has_tracking_pose)

Out of scope: blob stream B, fused C, fit CLI.

Acceptance: existing kpMS tests green; new test: manifest with H5 pose only (no sleap_path) builds coordinates.
```

---

## Prompt — T2c discovery has_tracking_pose

```
Scope: T2c only. Prerequisites: T2a.

Expose tracking availability in manifest CSV / discovery without requiring sleap_path column.

Touch: file_discovery.py, discovery_sync.py attrs, optional manifest column has_tracking_pose

Out of scope: GUI, fit.

Acceptance: unit test on synthetic manifest row.
```

---

## Prompt — T3a sidecar backfill + keep_live

```
Scope: T3a only. Prerequisites: T2b.

Backfill tracking/anatomical from .slp when missing; never overwrite pose_source=sleap_live unless overwrite flag true.

Touch: maze/pipeline/persist_pose.py (new), call sites in process_trial or virtual acq promotion path

Default: keep_live. Attr pose_superseded_at when overwrite.

Out of scope: GUI checkbox (T3b).

Acceptance: tests: live pose kept when sidecar import attempted without overwrite.
```

---

## Prompt — T3b overwrite UX

```
Scope: T3b only. Prerequisites: T3a.

User-visible pose overwrite control.

Touch: pipeline_dialogs.py Analyze path and/or settings_dialog.py; status_and_config_sync.py status strings per h5_tracking_contract.md

Out of scope: blob, kpMS fit.

Acceptance: pytest if dialog logic testable; manual test plan in PR description.
```

---

## Prompt — T4a kpMS stream B (blob)

```
Scope: T4a only. Prerequisites: T1d, T2b.

build_kpms_inputs variant for pose_stream=blob using tracking/blob from H5.

Deliverables:
- build_kpms_inputs_blob() or pose_stream param on build_kpms_inputs
- anterior/posterior idxs from motion heading helpers, not nose/tail
- apply.py + fit.py accept stream via internal config (CLI flags come in T4c)

Out of scope: fused stream C, WSL.

Acceptance: test with synthetic H5 blob data → non-empty coordinates dict.
```

---

## Prompt — T4b kpMS stream C (fused)

```
Scope: T4b only. Prerequisites: T4a.

Concatenate anatomical + blob tensors per frame; bodyparts = STANDARD_NODE_NAMES + BLOB_NODE_NAMES.

Handle partial validity: NaN + confidence 0 where stream missing.

Out of scope: T5 spike analysis, GUI.

Acceptance: test fused K=16; frame alignment identical frame_index between streams.
```

---

## Prompt — T4c --pose-stream CLI + GUI

```
Scope: T4c only. Prerequisites: T4a (T4b if fused in same PR is too large — do fused in T4b first).

Expose --pose-stream anatomical|blob|fused on maze-kpms-fit and maze-kpms-apply.

Default project subdirs: kpms/<stream>/<model_name>/ per tracking_kpms_master_plan.md.

Touch: fit.py parse_args, apply.py, kpms_fit_dialog.py, kpms_apply_dialog.py, fit_summary.json records pose_stream.

Out of scope: WSL JAX install.

Acceptance: pytest test_kpms_fit_config extended for pose_stream; CLI help text updated.
```

---

## Prompt — E0 ethogram materialize

```
Scope: E0 only (docs/ethogram_scope.md). Prerequisites: T2b for manifest/H5 alignment.

Implement maze/kpms/ethogram.py (RLE frames→bouts) + maze/kpms/materialize.py + maze-kpms-materialize CLI.

Read per-frame syllable from results_apply.h5; bout CSV only; tag pose_stream in export metadata when present.

Out of scope: run_exports bundle (E4), GUI status (E5), T4 streams beyond reading same results file.

Acceptance: uv run pytest tests/test_ethogram.py tests/test_materialize.py -q
```

---

## Prompt — T5 E6 spike (research)

```
Scope: T5 only. Prerequisites: T4c, E0.

Empirical comparison on small manifest subset (≤30 trials): fit/apply streams A, B, C with --max-trials 30.

Deliverables:
- scratch/ dated README with bout duration stats, overlay QC notes, recommendation defer/pursue C
- Optional: maze/cli/kpms_stream_ablation.py helper (no production default)

Out of scope: merging syllable taxonomies across streams.

Do not commit scratch/; summarize conclusions in PR or docs/tracking_kpms_master_plan.md § T5 findings.
```

---

## Phase T complete (regression-only mode)

```
Phase T (Tracking v2 + multi-stream kpMS paths) for OpenEthoMaze is complete through T4c and E0. Fix regressions only.

Checklist:
- tracking/anatomical + tracking/blob written at live acquisition (blob requires track_enable_backup; not virtual acq)
- build_kpms_inputs reads H5 first; three pose streams fit/apply independently
- keep_live overwrite UX shipped
- WSL GPU fit documented (phase_wsl_agent_prompt.md)

Do not reopen slices unless fixing a confirmed bug.
```
