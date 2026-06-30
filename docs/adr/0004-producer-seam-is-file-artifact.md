# The producer seam is the BehaviorLabeling file artifact

The seam across the three Behavior **producers** (A grammar, B B-SOiD/MotionMapper, D bout AR-HMM) is the on-disk **`BehaviorLabeling` artifact** (`behavior_frames.h5` + `behavior_bouts.csv` + `provenance.json`, see `docs/behavior_labeling_contract.md`), **not** a shared Python `BehaviorProducer` interface. Because Option B may run in an isolated environment / subprocess (ADR-0003), a process-level Python protocol spanning all producers would be the wrong seam — it cannot cross that boundary. A file artifact is language- and process-agnostic, so the evaluation harness depends only on the artifact and never on any producer's internals or environment.

## Consequences

- A future reader will look for a `BehaviorProducer` base class; there deliberately isn't one. Producers share an **output contract** (`maze/kpms/behavior_ethogram/labeling.py`), not a call interface.
- A same-process `BehaviorProducer` Protocol for *just* the Python producers (A and D) is allowed later for code locality, but it must terminate at producing a `BehaviorLabeling` so A/D cross the same seam B does.
- The evaluation harness (S1) and any consumer must read the artifact via `read_behavior_labeling` / the documented schema — never import producer modules to introspect results.
