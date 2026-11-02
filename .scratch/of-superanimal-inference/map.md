# Open-field SuperAnimal inference — wayfinder map

Labels: `wayfinder:map`

## Destination

A script, run in the DeepLabCut environment on the other machine, that calls `video_inference_superanimal` on every masked open-field mp4 (including Test 68) and writes pose files plus labeled overlays to `H:\Open Field - superanimal\`. It stops there. The OpenEthoMaze cohort file is a later effort.

## Notes

- Domain: open-field frailty pose. Model stays `superanimal_topviewmouse`, `hrnet_w32`, detector `fasterrcnn_resnet50_fpn_v2`.
- Tracker: local markdown (`.scratch/of-superanimal-inference/`).
- Skills: grilling, domain-modeling.
- Locked: `video_adapt=False`. `max_individuals=1`. `cropping` stays unset (the mask is already the region of interest). `create_labeled_video=True`. `plot_bboxes=True`. `batch_size` and `detector_batch_size` are arguments, default 4. One output folder, `H:\Open Field - superanimal\`. Input is every `*.mp4` directly in the masked-video folder, including Test 68.
- DeepLabCut environment, not the OpenEthoMaze `uv` env. Paths are arguments. Do not start the full cohort from a charting session.
- With adaptation off, `pcutoff` and `bbox_threshold` are passed only into the overlay writer. The detector postprocessor is built with `min_bbox_score` left unset, so those two knobs do not change which boxes receive a pose. `max_individuals` does: it caps how many detector boxes get a pose (`animal0`, `animal1`, …), ranked by detector score. A slot is not an identity across frames.
- Resume: `video_inference_superanimal` does not skip a finished video. The script calls it one mp4 at a time and skips a stem when both the pose HDF5 and the labeled mp4 are already in the dest folder. A failure is logged and the loop continues. The `_full.pickle` and the HDF5 are written after the frames are done, then the labeled mp4.
- Test 68: the other machine has a mask from tweaks that are not in this repo. This repo's floor fitter still flags Test 68. This map consumes the masked mp4 and does not re-fit the floor.
- Glossary candidates live in the DeepLabCut notes (`scratch/docs/DLC-notes/`), not a new file, until a term is resolved here.

## Decisions so far

- [Which knobs to smoke before the full run](issues/01-grilling-pre-run-knobs.md): `pcutoff` and `bbox_threshold` stay untouched. The 1-vs-2 clip plan in that ticket was superseded before any clip was run.
- [Which clips stand in for the smoke](issues/03-grilling-smoke-clips.md): no clips. `max_individuals` locks at 1. The masked set shows no second subject. The Test 1 still on this machine still includes cable pixels in the pose zone; the run keeps the single top box anyway.
- [What the inference script commits to](issues/02-grilling-script-contract.md): one DeepLabCut-scratch Python file, video folder and output folder as arguments, no baked-in drive letter. `plot_bboxes` on. One mp4 at a time. Skip a stem when its pose HDF5 and labeled mp4 already exist. Log a failure and continue.

## Not yet specified

## Out of scope

- OpenEthoMaze cohort HDF5, the frailty feature table, a centimeter scale, and a frailty index. This map ends at DeepLabCut pose files and overlays.
- Video adaptation and its training knobs (`adapt_iterations`, `pseudo_threshold`, `detector_epochs`, `pose_epochs`). Adaptation stays off.
- Choosing which slot is the open-field mouse. The run stores one slot.
- [Run the slot smoke and lock the cap](issues/04-task-run-slot-smoke.md): the 1-vs-2 clip comparison will not be run. The cap was locked without it.
- Back-porting the Test 68 floor-fit tweaks into this repo.
- Remapping the 27 TopViewMouse parts onto the maze 8-node skeleton, and any Keypoint-MoSeq use of these files.
