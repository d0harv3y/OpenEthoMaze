# Roadmap (Open Etho Maze)

This file is the **shared product wishlist** for OEM: direction and priorities, not day-to-day commands. Personal runbooks stay in `my_todo.txt` / `my_todo_kpms-viz.txt`.

## Pipeline and acquisition

- Re-enable and finish **Discovery** (sync / manifest / data roots) when the flow is stable.
- Re-enable **batch virtual acquisition** (pose inference from video, headless materialization) with clear skip-if-pose-exists rules and backend choice.
- **DeepLabCut** (or other backends) as an alternative to SLEAP, behind a single `InferenceBackend`-style abstraction; same contract into the rest of the pipeline.

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

## Platform and quality

- **Optional stacks in CI**: markers or smoke jobs for `kpms`, `sleap`, GPU; documented install matrix (lab PC vs HPC).
- **Observability**: run logging (manifest path, model dir, config snapshot, git hash) for long fits and batch inference.
- **Performance** outside kpMS: pipeline parallelism, HDF5 write patterns, headless profiles for large cohorts.

## Near-term narrative (single story)

Aim for one guided path documented end-to-end: **pose → (optional kpMS fit) → kpMS apply → unified overlay → export**, with the same manifest and preprocessing assumptions at each step.
