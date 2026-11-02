# Which knobs to smoke before the full run

Type: grilling
Status: resolved
Assignee: wayfinder session
Blocked by:

## Question

Before the full cohort, which SuperAnimal settings do we compare on a few masked videos, and what result locks `max_individuals` for the script?

The comparison has to be able to show whether a cable, a wall, or a second mouse takes the only pose slot. The sample must not be written into `H:\Open Field - superanimal\`, or the full run will skip those videos.

## Answer

Compare `max_individuals` 1 against 2 on two short masked clips: one whose pose zone reaches cables, and one with a clean floor. Write both settings to a scratch folder, not `H:\Open Field - superanimal\`. `plot_bboxes` on. `video_adapt` off. Leave `pcutoff`, `bbox_threshold`, and the adaptation knobs alone.

Lock the full run at 1 if `animal0` stays on the mouse for both clips. Lock it at 2 if a cable, a wall, or another mouse takes the only slot. A slot (`animal0`, `animal1`) is the detector's score rank on that frame, not an identity across frames.

Which stems, and how long the clips are, is a separate decision. The numeric cap is not locked until those clips have been run.

## Comments

- 2026-10-30: Superseded. The clip comparison was not run. The cap was locked at 1 in [Which clips stand in for the smoke](03-grilling-smoke-clips.md).
