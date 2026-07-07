# Mission: Discrete sequence models & syllable grammar

## Why
Turn kpMS **syllables** into portable ethological **behaviors** (“words”) using **discrete sequence** tools — n-grams, Markov context windows, and explicit grammar rules — that match how Option A (`maze-mine-syllable-grammar-candidates` → `grammar_rules.json`) actually works. Classical autoregression on continuous bout features is a separate producer (Option D), not the core metaphor.

## Success looks like
- Read a bout-level syllable stream and explain what an n-gram pattern means
- Describe **mine** (discover frequent patterns) vs **apply** (longest-match labeling) and why CSV sort ≠ apply precedence
- Curate conflicting subset/superset rules (e.g. `[3]` vs `[3,7,7]`) with correct longest-match intuition
- Connect Jurafsky-style n-gram / Markov ideas to `grammar_rule_contract.md` without confusing them with AR-HMM emissions
- Explain merge vs grammar vs LM/perplexity; interpret occupancy and transitions across manifest strata

## Constraints
- Teach from trusted sources; cite them in lessons
- Ground examples in OpenEthoMaze glossary (`CONTEXT.md`, `grammar_rule_contract.md`)
- Prefer interactive longest-match practice over probability algebra early on

## Out of scope
- Classical AR(p), ACF/PACF, stationarity (optional appendix — lesson 0001)
- kpMS Stage 2 float64 / `nlags` tuning (separate cheatsheet)
- Training transformer LMs from scratch (lesson 0004 covers n-gram LM + strata only)
- Option D bout AR-HMM as the primary “syllables → words” story
