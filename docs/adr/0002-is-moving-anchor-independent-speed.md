# is_moving anchor uses an independent speed source

Evaluation is bootstrapped from the coarsest anchor, `is_moving`, grown into finer behaviors over time. `is_moving` is derived from a **producer-independent** per-frame speed (legacy VAST ambulation XY / `spot_hybrid`), using hysteresis (enter/exit speeds) plus a minimum dwell expressed in **milliseconds** (converted via fps), with the threshold set at the speed-histogram antimode and the dwell chosen by a debounce sweep.

We deliberately do **not** derive the anchor from the kpMS centroid speed that Option D consumes: doing so would make "D recovers is_moving" partly tautological. Expressing the dwell in ms (not n_frames) and using hysteresis keeps the anchor portable across framerates and tasks, which is the project's stated goal. A future reader will wonder why the anchor ignores the convenient in-pipeline speed — this is why.
