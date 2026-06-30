# Behavior ethogram

Turning kpMS pose **syllables** into an interpretable, task-portable **behavior** sequence (the ethogram) that generalizes across tasks (open field, maze) rather than being tied to one cohort's syllable indices.

## Language

**Behavior**:
A contiguous run of frames carrying one label from an interpretable, task-portable set (e.g. locomote, rear, groom, freeze, turn, pause). A grammar-with-memory layer **above** syllables: the same syllable may belong to different behaviors depending on its sequence context.
_Avoid_: syllable, bout, motif, behavior_token (those are inputs or mechanisms, not the target)

**Syllable**:
A per-frame discrete state emitted by kpMS (keypoint-MoSeq) over egocentric pose; sub-second, cohort-specific, and not comparable across pose streams or models.
_Avoid_: behavior, motif, cluster

**Bout**:
A maximal run of consecutive frames sharing one syllable id (run-length encoding of the syllable stream). The unit Stage II/III currently summarize.
_Avoid_: behavior, episode, segment

**Merge**:
A *memoryless* syllable-id → syllable-id remap (collapse several syllable ids into one). Cannot express sequence context, so it is **not** a way to produce a Behavior.
_Avoid_: relabel, taxonomy (when sequence context is intended)

**Behavior token** (mechanism):
The Stage III bout AR-HMM state assigned to each bout (`fit_bout_arhmm`). One specific *producer* of Behavior (Option D), not the Behavior concept itself.
_Avoid_: behavior, label (unqualified)

**Producer**:
A method that emits Behavior labels over frames/bouts. Current candidates: Option A (syllable-sequence grammar relabeling), Option B (frame-level physical-feature states, B-SOiD/MotionMapper), Option D (enriched bout AR-HMM).
_Avoid_: model, pipeline (unqualified)

**Anchor signal**:
A cheaply-derived, producer-independent label used to *validate* producers (never to train them), grown incrementally from coarse to fine. Evaluation starts at the coarsest anchor and adds finer ones as confidence grows.
_Avoid_: ground truth, labels (unqualified), target

**is_moving**:
The first (coarsest) anchor: a binary per-frame signal of whether the animal is locomoting, derived by thresholding an independent speed estimate with temporal debounce/hysteresis to suppress threshold flicker. A validation anchor, distinct from the Behavior `locomote`.
_Avoid_: active, mobile, locomote (locomote is a Behavior; is_moving is a binary anchor)

**Behavior grammar** (Option A):
A per-fit mapping from characteristic syllable sequences to named Behaviors, *discovered* by mining the syllable stream then *curated and named* by a human. Re-derived on refit; only the behavior names are portable, not the underlying syllable-id rules. Substrate schema: `docs/grammar_rule_contract.md`.
_Avoid_: merge (memoryless), taxonomy (id-level only)

**anchor_bucket**:
Per-behavior harness tag (`moving`, `still`, `ignore`) assigned at curation time alongside the portable `behavior_name`. Lets ethological names (`groom`, `rear`) coexist with the only contracted anchor today (`is_moving`). `ignore` excludes a behavior from anchor scoring until a finer anchor exists.
_Avoid_: ground truth, is_moving (anchor_bucket is producer metadata for validation, not the anchor itself)

**Behavior labeling**:
The unified artifact every Producer must emit: a per-frame Behavior label stream on the source-video timeline, a derived bout-level CSV, and a provenance JSON. The common currency the evaluation harness scores. Schema: `docs/behavior_labeling_contract.md`.

**Bout scalar features** (Option D substrate):
Per-syllable-run kinematic summary rows for Stage II/III (clustering, AR-HMM). Schema: `docs/bout_feature_contract.md`.
_Avoid_: tokens CSV, results h5 (those are mechanism-specific)

**Producer seam**:
The place a Producer's interface lives: the on-disk `Behavior labeling` artifact, **not** a shared Python class. Producers share an output contract, not a call interface, so an isolated-env producer (Option B) crosses the same seam as the in-process ones. The harness depends only on this seam. See `docs/adr/0004-producer-seam-is-file-artifact.md`.
_Avoid_: BehaviorProducer interface/ABC, plugin API
