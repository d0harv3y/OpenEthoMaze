# Context Map

## Contexts

- [Dwell averaging](./CONTEXT.md) — pooling RUN-phase dwell heatmaps across animals and trial blocks in the legacy VAST database.
- [Behavior ethogram](./maze/kpms/behavior_ethogram/CONTEXT.md) — turning kpMS pose syllables into an interpretable, task-portable behavior sequence (the ethogram).

## Relationships

- **Both → TrialManifest**: every context keys on the same `TrialManifest` / trial keys `(animal_id, session, trial)`; ethogram bout/behavior tables join to ambulation trial CSVs on those keys.
- **Behavior ethogram → Dwell averaging**: shares the legacy VAST H5 (RUN-phase XY, `trial_state`) as a source of held-out kinematics for evaluation, but owns its own label artifacts.
