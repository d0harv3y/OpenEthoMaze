---
title: F NGramSeq-A
type: family
assay: nor-impress
status: lava
claim_kind: na
verdict: fail
tags:
  - claim/family
  - assay/nor-impress
  - lava
---
# F NGramSeq-A

**Family spec** (locked **2026-10-02** before peeking; recognition-grain pair-sequence).  
**Status:** lava — clean null. #lava  
**Parent (recog flavor):** also cited on [[H Recognition Separators]] as failed MoSeq grammar try at `nvl_obj`.  
**Parent (redundancy):** [[H Non-Recognition Condition Separators]] when read as sequence redundancy.  
**Members:** [[E NGramSeq Pair MI]] · [[E NGramSeq Bigram Richness]]  
**Verdict:** **fail** (0/4 FDR, 0/4 uncorrected). [[V NGramSeq Null]]

## Plain ask

At `NOR_TX` × `nvl_obj`, does `condition` separate fixed-budget adjacent-bout mutual information or bigram richness?

## Design strip (complete experiment)

| Axis | Lock |
|------|------|
| Cohort | `moseq_251017`, 144 animals |
| Model / alphabet | Pilot `paramscan_s1-1e8_s2-1e5_ss-50`; portable `cluster_id` (K=21) |
| Unit | Consecutive bout pairs after RLE |
| Budget | M = min transitions across animals (= **108** this run); floor 50; seed 7; same draw for both scalars |
| Metrics | `pair_MI` = I(X1;X2) bits (Laplace α=1.0 on K×K joint); `bigram_richness` = # distinct bigrams in draw |
| Reference | **None** (reference-free — no count laundering via TV-to-noSD) |
| Association | Kruskal by `condition` within sex |
| Family size | 2 × F/M = **4** (already **per-grain**; template for [[F NGramSeq-PerGrain]]) |
| Hit rule | `q_bh < 0.05` within NGramSeq-A |

## Outcome

| Cell | p | q_bh |
|------|---|------|
| F `pair_MI` | 0.126 | 0.503 |
| M `pair_MI` | 0.524 | 0.672 |
| F `bigram_richness` | 0.385 | 0.672 |
| M `bigram_richness` | 0.672 | 0.672 |

Medians flat (MI ≈ 0.15–0.17 bits). Cross-campaign exploratory (ladder raw / recog / per-animal): 0 FDR over 196 cells — see [[V NGramSeq Null]].

## Artifacts

→ [[Run NGramSeq]] (campaign root + CSVs + runner)

## Related

- Superseded stub: [[F NGramSeq-A Score Contract]]
- [[F NGramSeq-B]] · [[F NGramSeq-C]] · [[F NGramSeq-PerGrain]] · [[F TransStruct-A]]
- [[H Recognition Separators]] · [[H Non-Recognition Condition Separators]] · [[Joint vs Per-Grain FDR]]
