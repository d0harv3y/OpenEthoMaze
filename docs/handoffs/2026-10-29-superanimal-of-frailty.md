---
title: Handoff — SuperAnimal OF pose → frailty in OpenEthoMaze
date: 2026-10-29
from_workspace: DeepLabCut (+ lightly SSL / B-KinD side track)
to_workspace: OpenEthoMaze
tags:
  - handoff
  - deeplabcut
  - superanimal
  - frailty
  - open-field
---

# Handoff: SuperAnimal open-field pose → frailty index (root in OpenEthoMaze)

## Intent for next session

Move the chat/work home to **OpenEthoMaze**. SuperAnimal / DeepLabCut is a **pose factory** (not fully SSL); the **frailty index analysis** and claim vocabulary should live in OEM. Do not treat DLC Model Zoo as an SSL ladder item.

## Suggested skills (next agent)

Call the Skill tool for these as needed:

| Skill | When |
|-------|------|
| `obsidian-markdown` | Editing vault notes / wikilinks |
| `data-dictionary` | When a frailty run folder + `INFO_*.md` exists |
| `investigation` | If scaffolding a frailty / SuperAnimal integration investigation under `scratch/` |
| `composition-vocab` context via OEM `docs/vocab/` | Any stats / grain / D vs I wording (read `CONTEXT.md`, `STATS.md`, `FORMULAS.md`) |
| `handoff` | Further session boundaries |

Also follow repo `AGENTS.md` and OEM path rules (no lab drive letters as defaults in `maze/`).

## Artifacts to reuse (do not re-derive)

### DeepLabCut vault (spark notes)

In-repo Obsidian vault (SSL-notes style):

`C:\Users\admin\code\DeepLabCut\scratch\docs\DLC-notes`

- Hub: `DLC Index.md`
- Ladders: `MODEL-ZOO.md`, `API-LADDER.md`, `FRAILTY-LADDER.md`, `CONTEXT.md`, `INTERPRET.md`
- Failure cards already written: `frailty/Second Mouse Steal.md`, `Dropped Frames.md`, `Paw Gap.md`, `Wall Climb.md`
- API card with param table: `api/video_inference_superanimal.md`

Open folder as vault → start at DLC Index. Prefer linking/copying claim-facing frailty cards into OEM rather than duplicating Model Zoo spark notes.

### Smoke run (already executed on faster machine)

- Script: `DeepLabCut/scratch/smoke0.py`
- Outputs: `D:\DeepLabCut\out_superanimal_smoke\`
- Model: `superanimal_topviewmouse` + `hrnet_w32` + `fasterrcnn_resnet50_fpn_v2`
- `video_adapt=False`, `max_individuals=1`
- Video: `D:\Open Field - mp4\Test 1.mp4`
- h5: ~17770 frames × 27 bodyparts; individual `animal0`; **no paw keypoints** in TopViewMouse skeleton
- Drops: ~5% frames with `mouse_center`/`nose` likelihood &lt; 0.1; median gap length ~1 (max ~37) → interpolate/filter, not retrain
- Shoulders weaker than hips (~0.37–0.42 vs ~0.75 mean likelihood)

### DLC env note

`DeepLabCut/pyproject.toml` pinned PyTorch **cu124** sources so `uv` does not pull CPU torch. Prefer `uv run` with frozen lock after sync. User runs installs.

### Related but separate tracks

- **B-KinD** (`C:\Users\admin\code\BKinD`): animal-crop SLEAP prep scripts/config; circular ROI was a dead end for LEDs/rim; animal-centric crop preferred for SSL pose discovery. Not the frailty root.
- **lightly SSL-notes vault**: `lightly/scratch/docs/SSL-notes` — keep SSL there; pose factory comparison (SLEAP vs B-KinD vs DLC) can cross-link.
- OEM already has related research notes: `docs/research/gait_analysis.md`, `docs/research/rodent_brief_pause_ethology.md` — useful for frailty kinematics / immobility conflations; **no dedicated frailty module yet**.

## Decisions / facts locked in conversation

1. **TopViewMouse has no paws** — “weak paws” is a skeleton gap (`Paw Gap`). Need `superanimal_quadruped` or labeled transfer for paw-level frailty axes.
2. **`cropping=` is AABB only** `[x1,x2,y1,y2]` — no polygon/rotate in SuperAnimal API. Angled (~45°) arena → pre-process: mask outside polygon and/or rotate then AABB; or loose AABB if interloper only in leftover FOV triangles.
3. **Second-mouse steal**: with `max_individuals=1`, top detector box wins per frame. Fix order: ROI/mask → `max_individuals=2` + post-hoc geometry pick → not `video_adapt`.
4. **`video_adapt=True` (PyTorch)**: zero-shot on `videos[0]` → pseudo COCO dataset (`pseudo_threshold`, `bbox_threshold`) → short train `detector_epochs` + `pose_epochs` → re-infer `*_after_adapt`. One video intended to generalize. Does not add paws or identity lock. **`adapt_iterations` is TF/`dlcrnet` legacy** — ignored for hrnet path; use epochs.
5. Frailty claims need OEM-style **claim shape**: factory + skeleton + subject selection + grain + derived feature + frailty axis. Pose likelihood = QC, not FI.

## Landed in OEM (same day)

Roadmap now treats SuperAnimal TopViewMouse as the **primary pose estimator for open-field frailty** (SLEAP stays the maze live skeleton). Contract note: native 27-node `tracking/anatomical` plus a binned feature table (`bin_width_s` 600 now, 300 later), in a cohort H5 that is not maze `trials.h5`. See `docs/roadmap.md` § Open-field frailty and `docs/h5_tracking_contract.md`. Floor quadrilaterals: `maze-of-floor-quad`.

## Open work for OpenEthoMaze

- Corner mask is the four image triangles outside the floor diamond. The cohort is unlabeled on purpose; join animal / `condition` / age later. Row id stays the video id. No placeholder stratum.
- Quadrilateral is per video (`maze-of-floor-quad`, inner Hough creases). Review images gate the mask. Do not start the ~82 h pose batch until the flagged sheet is accepted.
- Feature rows are time bins (`video_id`, `bin_index`, `t0_s`, `t1_s`, `bin_width_s`). Current contrast: `bin_width_s=600` (first 10 min vs last 10 min) on videos with two full bins. Five-minute bins are `bin_width_s=300` on the same columns. ~10 min videos are one bin and stay out of the pair. `Test 3` and `Test 158` have no full 600 s bin.
- Root frailty runners and `INFO_*.md` once a run folder exists. v1 columns: path length, mean speed, immobility fraction, thigmotaxis fraction from `mouse_center`. Collapsed frailty-index formula still undeclared.
- Optional: port frailty claim cards from `DLC-notes` into `docs/vaults/openethomaze/`.

## Do not

- Push DeepLabCut fork changes to upstream unless asked.
- Put `D:\` / IMPRESS paths as defaults inside `maze/` package code.
- Call gaps in pose “immobility” or TopViewMouse shoulders “paws.”
- Assume `video_adapt` fixes interloper focus steal.

## Quick commands (reference)

```python
# DeepLabCut/scratch/smoke0.py pattern
deeplabcut.video_inference_superanimal(
    videos=[...],
    "superanimal_topviewmouse",
    model_name="hrnet_w32",
    detector_name="fasterrcnn_resnet50_fpn_v2",
    max_individuals=1,  # raise + select if FOV bleed
    video_adapt=False,
    cropping=None,  # or [x1, x2, y1, y2]
    dest_folder=...,
)
```

Shell for OEM work: **PowerShell**. Prefer `uv sync` / `uv run` per OEM `AGENTS.md`.
