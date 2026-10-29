# Include Hill q=2 / dominance on the deck?

Type: grilling
Status: resolved
Blocked by: 02

## Question

**Corrected framing (2026-10-08):** Hill q=2 / dominance is **already computed and figured**. This ticket is **not** "write a new runner."

Does slide 3 **show** the existing prox hill2 panels (richness → Shannon → Hill q=2 / dominance ladder), or keep the slide to shannon+richness only?

## Answer

**Yes — show hill2**, and **re-analyze condition with one BH family per scalar** (user 2026-10-08).

Executed as [[F ProxComp Per-Scalar Score Contract]] / [[Run ProxComp Per-Scalar]] / [[V ProxComp Per-Scalar Null]]:

- Families: ProxComp-Shannon, ProxComp-Richness, ProxComp-Hill2 (each m=2 F/M)
- Assay litmus: all three (+ time) **pass**
- Condition: **0/2 FDR in every scalar family** (same story as joint ProxComp-A)
- Arts: `simpler_first_prox_comp_per_scalar_fams/`
- Runner: `simpler_first_prox_comp.py --per-scalar-families`

Sealed joint ProxComp-A lava untouched. Deck may use richness → Shannon → hill2 ladder + min0 fig pack; condition claim stays null under the new family design.
