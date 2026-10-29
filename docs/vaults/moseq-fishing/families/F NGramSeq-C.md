---
title: F NGramSeq-C
type: family
assay: nor-impress
status: lava
claim_kind: na
verdict: na
tags:
  - claim/family
  - assay/nor-impress
  - lava
---
# F NGramSeq-C

**Family spec** (locked **2026-10-05** before peeking; **complete NOR level grid**).  
**Parent:** [[H Non-Recognition Condition Separators]] / [[T0 Altered Behavior]].  
**Status:** lava — clean null on FDR. #lava  
**Verdict:** [[V NGramSeq Full Grid Null]]  
**Parallel to:** [[F TransStruct-C]].  
**Multiplicity posture:** **joint panel** (m=48). Commensurate per-grain bar: [[F NGramSeq-PerGrain]] / [[Joint vs Per-Grain FDR]].

## Plain ask

Across all 12 level grains, does `condition` separate fixed-budget pair MI / bigram richness?

## Design strip (complete experiment)

| Axis | Lock |
|------|------|
| Grains | Same 12 as TransStruct-C |
| Metrics | `pair_MI`, `bigram_richness` |
| Budget | Per grain M = min transitions (floor 50); seed base 7 + grain index |
| Family size | **48** |
| Hit rule | `q_bh < 0.05` within NGramSeq-C |

### Per-grain M (this run)

| session | no_obj | id_obj | nvl_obj |
|---------|-------:|-------:|--------:|
| `NOR_BL` | 193 | 116 | 87 |
| `NOR_TX` | 129 | 89 | 108 |
| `NOR_REC3hr` | 131 | 79 | 119 |
| `NOR_REC11hr` | 86 | 142 | 64 |

## Outcome

**0/48 `hit_fdr05`.** Three uncorrected `hit_p05` only — see verdict.

## Artifacts

→ [[Run NGramSeq Full Grid]] (campaign root + CSVs + runner)

## Related

- [[F TransStruct-C]] · [[F NGramSeq-B]] · [[F NGramSeq-PerGrain]] · [[H Non-Recognition Condition Separators]] · [[V NGramSeq Full Grid Null]]
- [[Joint vs Per-Grain FDR]]
