# Handoff — Behavior ethogram producers (A/B/D) + evaluation

**Date:** 2026-06-29 · **Next focus:** build **S1** (evaluation harness + `is_moving` anchor) on top of the S0 contract.

This doc is a pointer map, not a re-explanation. Decisions live in ADRs/CONTEXT; read those.

## Goal (one line)

A generalizable, task-portable **ethogram**: produce interpretable **Behavior** labels above kpMS syllables, via three competing **producers**, and evaluate which is best — bottom-up from an `is_moving` anchor (no hand-labeled set exists yet).

## Canonical context (read first)

- Glossary: [`maze/kpms/behavior_ethogram/CONTEXT.md`](../../maze/kpms/behavior_ethogram/CONTEXT.md); map: [`CONTEXT-MAP.md`](../../CONTEXT-MAP.md)
- ADRs: [`docs/adr/0001`](../adr/0001-behavior-producer-agnostic-target.md) (producer-agnostic Behavior), [`0002`](../adr/0002-is-moving-anchor-independent-speed.md) (independent-speed anchor), [`0003`](../adr/0003-bsoid-resolver-gate-and-boundary.md) (B-SOiD env gate), [`0004`](../adr/0004-producer-seam-is-file-artifact.md) (producer seam = file artifact)
- Artifact schema: [`docs/behavior_labeling_contract.md`](../behavior_labeling_contract.md)
- Superseded pre-grill plan (do not cite): `scratch/archive/behavior_ethogram_2026-06-24_pre-grill/` (+ its `SUPERSEDED.md`)

## Slice plan

`S0 contract → S1 harness+is_moving → { S2 Option D ∥ S3 Option A ∥ S4 Option B } → S5 bake-off`

- **S0 — DONE.** `maze/kpms/behavior_ethogram/labeling.py` (`BehaviorLabeling`, `TrialFrameLabels`, `labeling_to_bouts`, `write_/read_behavior_labeling`), path helpers in `paths.py`, exports in `__init__.py`, tests `tests/test_behavior_labeling.py` (15 tests green; ruff+black clean). Zero new deps (HDF5 not parquet — pyarrow absent).
- **S2 — Option D.** Extend `bout_scalars.py`: add `bout_net_dheading_rad` (signed turn) + `bout_straightness` (net/path ∈ [0,1]); fix circular heading (sin/cos); drop `cluster_id`-as-float; add low-D **syllable kinematic-signature embedding** (pooling-safe, Gaussian-valid — never raw id/one-hot). Emit the S0 artifact. PCA/correlation-check the embedding adds independent signal.
- **S3 — Option A.** Mine candidate syllable sequences → exemplar tray → human-curated **per-fit rule table** (discover→curate) → apply grammar → S0 artifact. Portability is at the behavior-*name* level only (syllable ids non-comparable across seeds).
- **S4 — Option B.** Upstream **B-SOiD first** (MotionMapper later). Gate on a uv resolver spike (ADR-0003); isolated env + file boundary fallback. Pose-export adapter → import frame labels → S0 artifact.
- **S5 — bake-off.** Run S1 across producers; comparison report (consider a canvas); grow anchor beyond `is_moving` (rear/freeze/turn).

## S1 design constraints (carry these in — from /codebase-design pass)

1. **`is_moving` accepts speed; it does not fetch it.** Pure deep module: `(per-frame speed, fps, enter/exit thresholds, min_dwell_ms) → bool array` via hysteresis + min-dwell. A thin adapter loads the **independent** legacy-VAST speed and feeds it (ADR-0002). Calibrate threshold = speed-histogram **antimode**; pick min-dwell by a **debounce sweep** (resolves squishware's n_frames reservation with data). Express dwell in **ms** (÷fps), never frames.
2. **Harness depends only on the file seam.** Reads `BehaviorLabeling` artifacts + the anchor; never imports producer modules (ADR-0004).
3. **First task of S1:** verify the legacy-VAST H5 per-frame speed/`trial_state` schema on disk and confirm source-frame alignment via `maze.kpms.frame_alignment` — this is the spot flagged as possibly messier than assumed.
4. Metrics: cross-seed reproducibility, predictive validity vs held-out legacy kinematics, anchor-agreement; exemplar movies via `scripts/kpms_review_artifacts.py`.

## Data / env

- kpMS root: `C:\Users\admin\Documents\work\sack\test2` (5 anatomical seeds: 005/013/042/067/111; ~575k bouts; clustered table at `behavior_ethogram/stage_ii/bout_features_clustered.csv`). Legacy DB: `C:\Users\admin\Documents\work\sack\test\vast_results_legacy.h5` (and a copy under `sack\`). Manifest: `...\test2\trial_manifest_kpms_tracking.csv`.
- Env: jax hard-pinned `<0.7` (kpMS 0.6.3 + tfp); numpy 1.26.4; torch via `sleap` extra; **tensorflow absent**. Adding B-SOiD's TF risks the jax/kpMS pin — hence ADR-0003. User runs installs.
- Commands: `uv run ruff check maze tests` · `uv run black --check .` · `uv run pytest tests/test_behavior_labeling.py -q`.

## Open items

- Stray `scratch/2026-06-24-compile-bout-features-empty/diagnose.py` — not archived (user wasn't asked); fold into `scratch/archive/` if desired.
- **ADR-0005 candidate (not written):** "syllable identity encoded as physical embedding, never raw id/one-hot" rationale (Q5). Offer to the user.
- `my_todo.txt` has the older manual command sequences (compile-bout-features → cluster → fit-arhmm) — these are the *current Option-D substrate*, to be modified in S2, not archived.

## Suggested skills (next session)

- `/codebase-design` — keep the deep-module/seam lens when shaping the S1 harness + `is_moving` interfaces (consider `DESIGN-IT-TWICE.md` for the harness interface).
- `/tdd` — S1 metrics and `is_moving` debounce/hysteresis are pure and ideal for test-first.
- `investigation` (`C:\Users\admin\.cursor\skills\investigation\SKILL.md`) — for the S1-first task of tracing the legacy-VAST speed/state schema + frame alignment.
- `/grill-with-docs` — only if S1 metric-weighting or anchor-growth policy needs another decision pass.
