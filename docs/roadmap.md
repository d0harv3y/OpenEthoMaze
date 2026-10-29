# Roadmap (Open Etho Maze)

This file is the **shared product wishlist** for OEM: direction and priorities, not day-to-day commands. Personal runbooks stay in `my_todo.txt` / `my_todo_kpms-viz.txt`.

## Pipeline and acquisition

- Re-enable and finish **Discovery** (sync / manifest / data roots) when the flow is stable.
- Re-enable **batch virtual acquisition** (pose inference from video, headless materialization) with clear skip-if-pose-exists rules and backend choice.
- **Maze live pose** stays SLEAP on the 8-node skeleton (`STANDARD_NODE_NAMES`) until a separate decision. **Open-field frailty** uses SuperAnimal as the primary pose estimator (see below); it replaces SLEAP on that assay.

## Analysis and GUI

- **SLEAP trace quality** settings: decide where they live (analysis dialog vs pipeline), wire **preview parity** for trace stack, then re-enable any UI that was intentionally disabled until preview matches pipeline behavior.
- **Treatment / cohort table**: in-app editor or guided CSV workflow (replacing placeholder “create new” flows where they exist).
- **QC at scale**: batch or summary views that tie **mistrial reasons** to actionable fixes, not only per-trial artifacts.

## Keypoint-MoSeq (kpMS)

- **Model fit** in-product: thin CLI entry and/or GUI worker calling `maze.kpms.fit` (shared preprocessing with `apply`; no duplicated logic).
- **Syllable merge** tool surfaced in the same “behavior” story as apply (CLI already exists; unify UX and docs).
- **Sane classification** after merges: naming, stable IDs, and export conventions so merged syllables stay interpretable across sessions and tasks.
- **Unified overlay of behavior**: one coherent story from pose + syllables + exemplars (VAST / RAM / NOR parity where the science requires it).
- **Speed**: profiling and options (batching, I/O, subset policies, checkpoint reuse) without changing scientific defaults silently.

## Data contract and exports

- **Task-aware exports** and warnings when mixing tasks; document which columns are comparable across `circular` vs `radial_arm` (and others).
- **Controller vs legacy preflight**: keep `prefilter_mode` (or equivalent) explicit in docs so batch runs are reproducible and support knows what was enforced.
- **NWB interchange (potential)**: align frozen / export layouts with [Neurodata Without Borders](https://nwb-schema.readthedocs.io/en/latest/index.html); candidate add-in **[NeuroConv](https://neuroconv.readthedocs.io/)** for OEM→NWB conversion (SLEAP / DLC / video interfaces exist; maze trial H5 would need a custom `DataInterface`). See [tickets/unified-ultra-legacy-h5.md](tickets/unified-ultra-legacy-h5.md). Not an installed extra yet.

## Platform and quality

- **Optional stacks in CI**: markers or smoke jobs for `kpms`, `sleap`, GPU; documented install matrix (lab PC vs HPC).
- **Observability**: run logging (manifest path, model dir, config snapshot, git hash) for long fits and batch inference.
- **Performance** outside kpMS: pipeline parallelism, HDF5 write patterns, headless profiles for large cohorts.

## Open-field frailty (SuperAnimal primary)

SuperAnimal `superanimal_topviewmouse` (`hrnet_w32`, detector `fasterrcnn_resnet50_fpn_v2`) is the primary pose estimator for open-field frailty. It replaces SLEAP for that assay. DeepLabCut stays the pose factory; the frailty battery and claim vocabulary live here. Model Zoo is not an SSL ladder item. Lab video paths stay in CLI / `paths_local`, never as defaults inside `maze/`.

Cohort on disk (2026-10-29): `D:\Open Field - mp4`, `Test 1.mp4`–`Test 254.mp4`, 640×480, ~82 h. Most files are ~20 min; `Test 1`–`Test 2` and `Test 4`–`Test 13` are ~10 min; `Test 158` is ~5 min; `Test 3` is ~12 s. Smoke pose already exists for `Test 1` (`D:\DeepLabCut\out_superanimal_smoke\`).

Guided path:

1. **Corner mask.** The floor is a diamond in the frame. Preprocess writes a derived video with pixels outside that floor quadrilateral masked — the four image-corner triangles — so cables and adjacent boxes cannot win the detector. SuperAnimal `cropping` is an axis-aligned box and cannot express the diamond. Keypoints stay in the original camera frame. The quadrilateral is **per video** (`maze-of-floor-quad`): temporal median, an inner Hough seed, then each side snapped to the dark floor-wall crease using the middle of the side so the corner posts do not vote. Brightness segmentation is the rejected method (89/254 clean floors; 165 grew onto a bright wall; census `D:\DeepLabCut\of_frailty\quad_census.csv`). Review images gate the mask. Do not reuse one polygon for the cohort. Short files (`Test 3` ~12 s, `Test 158` ~5 min) stay flagged.
2. **Pose.** Zero-shot, `video_adapt=False`, `max_individuals=1` after the mask. Inference runs in the DeepLabCut environment. OEM ingests the resulting h5. If a file still shows a second-animal steal, rerun that file at `max_individuals=2` and keep the detection inside the floor polygon.
3. **Cohort HDF5**, separate from maze `trials.h5`:
   - `tracking/anatomical`: `xy` `(T, 27, 2)`, `score` `(T, 27)`, `node_names` = the TopViewMouse list, `pose_source=superanimal_topviewmouse`. Same dataset layout as [h5_tracking_contract.md](h5_tracking_contract.md). kpMS stream A still stacks `STANDARD_NODE_NAMES` (that list includes paws). This file stays off that reader until an explicit alias map exists.
   - **Binned feature table.** One row is a time bin inside the session (the video), with columns `video_id`, `bin_index`, `t0_s`, `t1_s`, `bin_width_s`, plus path length, mean speed, immobility fraction, and thigmotaxis fraction from `mouse_center`. This is not a maze `interval` (`run` / `wait`). `bin_width_s` is a parameter. The contrast asked for now is `bin_width_s = 600`: a ~20 min video yields bin 0 `[0, 600)` and bin 1 `[600, duration]`, which is the first 10 min and the last 10 min. A ~10 min video yields one bin and stays out of that pair. `Test 3` and `Test 158` yield no full 600 s bin. Five-minute bins are the same columns with `bin_width_s = 300` (four rows on a 20 min video). A remainder shorter than 2 s is absorbed into the last bin; a longer remainder is omitted rather than called a bin. Pose likelihood stays quality control. A collapsed frailty-index column waits on a declared formula. The cohort is **unlabeled on purpose**: there is no animal id, `condition`, or age column until a key file is joined. First vs last is a within-video pair. There is no between-animal test until labels exist.

v1 battery is locomotion and thigmotaxis. Paw gait and rearing wait on `superanimal_quadruped` or labeled transfer. TopViewMouse has no paw keypoints; shoulders and hips are not paws.

Claim shape for every frailty number: factory + skeleton + which animal slot + grain (bin inside the session) + `bin_width_s` + derived column + frailty axis. Handoff: [handoffs/2026-10-29-superanimal-of-frailty.md](handoffs/2026-10-29-superanimal-of-frailty.md).

## Near-term narrative

Two guided paths:

- **Maze:** pose → (optional kpMS fit) → kpMS apply → unified overlay → export, with the same manifest and preprocessing assumptions at each step.
- **Open field:** per-video floor quadrilateral → corner-masked video → SuperAnimal TopViewMouse → cohort HDF5 (27-node pose + binned feature table).
