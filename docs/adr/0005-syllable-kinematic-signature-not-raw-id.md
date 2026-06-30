# Syllable identity in AR-HMM features is a kinematic signature, not raw id

Stage III bout AR-HMM (Option D) must condition on syllable-level context without treating `raw_syllable_id` or HDBSCAN `cluster_id` as numeric features. Those ids are categorical, seed-specific, and invalid under Gaussian observation models (jax_moseq AR-HMM).

## Decision

Pool bout scalars by `raw_syllable_id` into a fixed **3-D kinematic signature** per syllable (mean speed, mean |dheading|, mean blob area). Append these `syllable_sig_*` columns to the bout feature matrix at sequence-build time. Never pass raw syllable id, cluster id, or one-hot syllable identity into AR-HMM features.

Heading direction (when enabled) uses sin/cos components, not raw radians.

## Consequences

- `include_cluster_feature` and `cluster_id` as AR-HMM inputs are rejected (S2).
- Signatures are recomputed from the bout table rows in the fit cohort, so they remain pooling-safe and comparable within a fit scope.
- Cross-seed syllable id portability is still not assumed; signatures encode physics, not identity.
