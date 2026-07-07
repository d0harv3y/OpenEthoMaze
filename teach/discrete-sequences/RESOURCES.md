# Discrete sequence models & grammar — Resources

## Knowledge

- [Chapter 3: N-gram Language Models — Jurafsky & Martin, SLP3](https://web.stanford.edu/~jurafsky/slp3/3.pdf)
  Markov assumption, bigram/trigram intuition, why finite context windows. Use for: formal n-gram vocabulary alongside lessons.

- [OpenEthoMaze: grammar rule contract](../../docs/grammar_rule_contract.md)
  Mine → curate → apply workflow, longest-match semantics, subset/superset curation. Use for: **primary lab mapping**.

- [OpenEthoMaze: behavior ethogram CONTEXT](../../maze/kpms/behavior_ethogram/CONTEXT.md)
  Syllable vs bout vs Behavior vs grammar vs merge. Use for: terminology discipline.

- [OpenEthoMaze: ADR-0001 producer-agnostic target](../../docs/adr/0001-behavior-producer-agnostic-target.md)
  Why grammar (A) and AR-HMM (D) are competing producers, not one model. Use for: mission framing.

- [Lecture notes: N-grams — Williams CS375](https://www.cs.williams.edu/~kkeith/teaching/f24/cs375/attach/ngrams.pdf)
  Compact MLE bigram estimator. Use for: optional probability follow-up after lesson 0002.

## Wisdom (Communities)

- [Cross Validated — ngram tag](https://stats.stackexchange.com/questions/tagged/n-gram)
  Pattern-frequency and Markov questions. Use for: “why longest context?” style checks.

- [keypoint-MoSeq discussions](https://github.com/dattalab/keypoint-moseq/discussions)
  Syllable semantics in pose streams. Use for: what syllables are *not* (not portable behavior names).

- [OpenEthoMaze: behavior token review / summarize](../../docs/behavior_token_review_contract.md)
  Occupancy, session trends, transitions; token vs ethology grain. Use for: strata evaluation (lesson 0004).

- [OpenEthoMaze: CONTEXT merge vs grammar](../../maze/kpms/behavior_ethogram/CONTEXT.md)
  Use for: lesson 0004 merge boundaries.

## Gaps

- Shipped CLI for syllable-level bigram perplexity / strata LM comparison — lesson 0004 is conceptual; scratch script on request.

## Appendix (deprioritized track)

- [Lesson 0001: What is autoregression?](lessons/0001-what-is-autoregression.html) — continuous AR; useful for Option D emissions only.
- Berkeley Stat 153 AR notes, Brockwell & Davis — see git history of this file if needed.
