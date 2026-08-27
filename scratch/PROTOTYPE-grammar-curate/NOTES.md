# Verdict (fill after driving the prototype)

**Question answered:** Should curation carry ethology names only, or also harness buckets?

**Decision:** **C** — `behavior_name` (portable ethology) + `anchor_bucket` (`moving` / `still` / `ignore`) until more anchors exist.

**Decision (Q2):** **B** — bucket map in `grammar_rules.json`, copied to S0 `provenance.json` as `behavior_anchor_buckets`; harness reads producer artifact only (ADR-0004).

**Decision (Q3):** **A+** — auto-enrich candidates with bout scalars at mine time; **mandatory exemplar overlay** before naming rows flagged ambiguous.

**Decision (Q4):** **B** — auto `must_review_overlay` from bout `ambiguous` + speed gray-zone + low-speed/high-dheading heuristics; `build-grammar-rules` warns/refuses without review unless `--force`.

**Decision (Q5):** **B** — `anchor_bucket` is per `behavior_name`; build step fails if the same name maps to conflicting buckets across rules.

**Decision (Q6):** **A** — `reviewed_at` (+ optional `reviewed_trial_key`) in `candidate_sequences.csv`; build blocks flagged rows with names but no review stamp.

**Decision (Q7):** **B** — document first; codified in `docs/grammar_rule_contract.md` (§ Curation workflow, subset ranking, max_n).
