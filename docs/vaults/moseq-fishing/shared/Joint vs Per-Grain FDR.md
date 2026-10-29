---
title: Joint vs Per-Grain FDR
type: ops
assay: nor-impress
status: na
claim_kind: na
verdict: na
tags:
  - claim/ops
  - assay/nor-impress
---
# Joint vs Per-Grain FDR

How Benjamini–Hochberg (**BH**) **family size** relates across sequence families.

## Two multiplicity postures

| Posture | What the family answers | m (TransStruct / NGramSeq) | Commensurate with A? |
|---------|-------------------------|----------------------------|----------------------|
| **Joint panel** | “Anywhere on this grain *panel*?” — one BH over all sex × metric × grain cells | B = 24; C = 48 | **No** — harder list-keeping than A’s m=4 |
| **Per-grain** | “At *this* `session × trial`, same bar as A?” — BH within each grain only | **4** per grain (2 metrics × F/M) | **Yes** |

**A** (`NOR_TX` × `nvl_obj`) is already per-grain (one grain → m=4).

**B / C** as shipped are **joint** panels. Do not read them as “A repeated at more grains with the same q bar.”

## Why both can exist

- **Joint** = honest saturation / “somewhere on the board” claim; multiplicity tax is the price of the joint sentence.
- **Per-grain** = commensurate with recognition-grain A; each grain is its own shopping list.

They are **different declared experiments** on the same Kruskal **p** columns — not two ways to quote one q.

## Honesty when re-cutting multiplicity

Re-applying BH per grain on already-computed tests_long tables does **not** recompute scalars, but the raw **p**s were previously visible under joint B/C. Label that on the PerGrain family notes. Do **not** promote a joint near-miss by silently shrinking m after peeking without a new contract.

## Related

- [[F TransStruct-A]] · [[F TransStruct-B]] · [[F TransStruct-C]] · [[F TransStruct-PerGrain]]
- [[F NGramSeq-A]] · [[F NGramSeq-B]] · [[F NGramSeq-C]] · [[F NGramSeq-PerGrain]]
- [[Claim Kind]] · [[Artifact Linking]]
