# What the inference script commits to

Type: grilling
Status: resolved
Assignee: wayfinder session
Blocked by:

## Question

Once `max_individuals` is locked, what does the runnable script commit to: file location, arguments, video selection, overlay flags, and resume behavior?

The script runs in the DeepLabCut environment. It does not build the OpenEthoMaze cohort file.

## Answer

One Python file in the DeepLabCut scratch tree. The masked-video folder and the output folder are arguments. No drive letter is written into the file.

`plot_bboxes` is on. `create_labeled_video` stays on. The call is one masked mp4 at a time, for every `*.mp4` directly in the videos folder.

Skip a stem when that stem's pose HDF5 and its labeled mp4 are already in the output folder. If a video raises, log the stem and continue with the next one. A crash mid-video leaves no HDF5, so that stem runs again.
