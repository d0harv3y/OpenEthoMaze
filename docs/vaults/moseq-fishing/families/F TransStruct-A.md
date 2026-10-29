---
title: F TransStruct-A
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
# F TransStruct-A

**Family spec** (locked before peeking; pattern for future families).
**Multiplicity posture:** **per-grain** (single grain → m=4). Commensurate template for [[F TransStruct-PerGrain]]. See [[Joint vs Per-Grain FDR]].
**Cells:** 2 metrics (`trans_dist_to_nosd_ref`, `H_next_given_curr`) × F/M = **4** Kruskal cells at `NOR_TX` × `nvl_obj`.
**Hit rule:** `hit_fdr05` ⇔ `q_bh < 0.05` within this family. Pass ⇔ ≥1 hit. Fail ⇒ stop, no Family B without user OK.
**Members:** [[E TransStruct TV Distance]] · [[E TransStruct Conditional Entropy]]
**Alphabet lock:** portable cluster_id, pilot `paramscan_s1-1e8_s2-1e5_ss-50` raw, Laplace α=1.0, min 20 bouts.
**Verdict:** **fail** (0/4 FDR, 0/4 uncorrected).

## Artifacts

→ [[Run Transition Structure]] (campaign root + CSVs + runner)

## Related

- [[V TransStruct Null]] · [[H Recognition Separators]] · [[H Non-Recognition Condition Separators]]
- [[F TransStruct-B]] · [[F TransStruct-C]] · [[F TransStruct-PerGrain]] · [[Joint vs Per-Grain FDR]]
