# Discrete sequences & syllable grammar — Glossary

Vocabulary for this teaching workspace. Aligns with [`CONTEXT.md`](../../maze/kpms/behavior_ethogram/CONTEXT.md) where noted.

## Terms

**Syllable**:
Per-frame discrete kpMS pose state; cohort-specific, sub-second. Not a portable behavior name.
_Avoid_: word, behavior, token (unqualified)

**Bout**:
Maximal run of one syllable id along the syllable stream. Elements of grammar patterns.
_Avoid_: behavior, frame

**Behavior**:
Portable ethological label (`groom`, `rear`, …) over contiguous frames/bouts. The target “word.”
_Avoid_: syllable, behavior_token

**N-gram (pattern)**:
Length-\(n\) sequence of discrete symbols (here: syllable ids at bout grain). Mined by frequency in Option A.
_Avoid_: AR lag, embedding

**Markov context**:
Assumption that the label at position \(t\) depends only on the previous \(n{-}1\) symbols, not the full history. Grammar uses explicit finite patterns instead of estimated \(P(\cdot)\).
_Avoid_: autoregression (continuous)

**Mine**:
Discover frequent bout-level n-grams → `candidate_sequences.csv`. Ranking by count is for **curation UX**, not labeling.
_Avoid_: fit, train (when meaning apply)

**Apply**:
Greedy **longest-match** scan left-to-right with curated rules → behavior names per bout. Precedence: longer pattern, then priority.
_Avoid_: CSV row order

**Grammar-with-memory**:
Same syllable id can mean different behaviors depending on neighboring bouts; resolved by overlapping rules and longest match — not by memoryless merge.
_Avoid_: merge, cluster_id

**Perplexity**:
Average “surprise” of a test sequence under an LM; lower means transitions were more predictable. QC for merge/refit/strata comparison — not a behavior name.
_Avoid_: accuracy, loss (unqualified)

**Syllable merge (kpMS)**:
Memoryless remap collapsing several raw syllable ids into one (`maze-kpms-apply-syllable-merge`). Changes occupancy marginals; does not encode context-dependent Behavior.
_Avoid_: grammar, relabel with memory

**Occupancy (strata)**:
Duration- or bout-fraction of time in a label per manifest stratum (tx, sex, strain, optional session). From `maze-summarize-behavior-tokens` or bout-table aggregation for raw syllables.
_Avoid_: count without normalization

**Transition summary**:
Bout-to-bout bigram counts between labels — discrete first-order chain; shipped as `transitions.csv` for behavior tokens/ethology.
_Avoid_: grammar apply rules
