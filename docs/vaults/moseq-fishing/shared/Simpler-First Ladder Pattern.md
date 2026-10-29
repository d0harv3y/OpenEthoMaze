---
title: Simpler-First Ladder Pattern
type: ops
assay: nor-impress
status: na
claim_kind: na
verdict: na
tags:
  - claim/ops
  - assay/nor-impress
---
# Simpler-First Ladder Pattern (shared bridge)

Assay-agnostic analysis pattern used by every kpMS campaign in this vault.
Assay claim graphs ([[NOR IMPRESS Index]], [[VAST Alz Index]]) link here
instead of run-to-run cousin links — do not mix strata across assays.

## Ladder (per campaign, in order)

1. **Descriptives** — bout inventory, duration structure per syllable.
2. **Kinematics** — bout-mean scalars (speed, heading change, size proxy).
3. **Signatures + cluster** — equate alphabets in z-scored kinematic space
   (HDBSCAN); raw ids are never portable (ADR-0005 lineage).
4. **DA / composition** — differential abundance, Shannon/richness/BC companions.
5. **Claim tests** — pre-declared families with BH (Kruskal rank primary);
   honesty passes record pass/fail per family.

Runners: `scratch/nor_object_mi/` (NOR), `scratch/vast_moseq/` (VAST; shared
DA primitives live in the NOR folder).

## Per-assay wire (not interchangeable)

- NOR: `session` × `trial` (`nvl_obj`…) × `condition` (`noSD`/`GHSD`/`RBSD`) — see PROTOCOL-STRATA.
- VAST: sessions `S01`…`S05`, trial windows `early_t1-3`/`mid_t4-6`/`late_t7-9`, 4 strain×tx×sex conditions.

## Related

- [[NOR IMPRESS Index]]
- [[VAST Alz Index]]
- [[Campaign Roots]]
