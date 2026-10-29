# Join board figure contracts

Type: grilling
Status: resolved
Blocked by: 01, 03

## Question

What exact join boards must be built (or reused) for slides 1–2 / 4?

## Answer

Settled 2026-10-09.

### Alphabet / model

**Exemplar only:** `paramscan_s1-1e7_s2-3e4_ss-100`.  
Do **not** use portable `cluster_id` / cluster ProxComp panels for this deck. Rebuild composition + session-step boards on this model's `raw_syllable_id` alphabet. Consensus mention = prose only.

Pause syllable: **raw_id 5** on that model (maps to cluster13 — brand as pause syll5).

### Boards

| Board | X | Y | Grain | Action |
|-------|---|---|-------|--------|
| **A** | classic investigation DR | `dr_time_prox` | animal × `NOR_TX` × `nvl_obj` (eligible) | **BUILD** scatter + Spearman + INFO |
| **B** | classic investigation DR | object-prox occupancy DR | same | **REUSE** `fig_classic_vs_object_prox` |
| **C** | `frac_still` (or immobile fraction) | syll5 **level** frame-share | animal × session × trial (full ladder) | **BUILD** scatter + Spearman + INFO; recognition inset optional |
| **D** | classic DR | `dr_shannon_prox`, `dr_richness_prox`, `dr_hill2_prox` | same as A | **BUILD for v1** (prefer have-and-cut over reopen grill) — exemplar alphabet |

### Slide 2 composition panels

Rebuild ProxComp-style **violins / Kruskal** for shannon / richness / hill2 on the **exemplar model** (not `fig_cluster_prox_*`). Prefer N=10 eligibility to match per-scalar contract; cite [[V ProxComp Per-Scalar Null]] only in vault, not on PPT.

### Out of scope for these boards

- Quadrant ROI panels
- Cluster_id figure pack as primary art
- Trial-step lattices
