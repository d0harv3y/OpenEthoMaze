---
name: stimulus MI sliced factorial
overview: Stratified one-hold and two-hold simple-effect group tests on pooled MI and when-metrics (career + within-session), with BH-FDR in four families; CLI --sliced-tests.
todos:
  - id: within_session_delta
    content: "Add early_late_delta_within_session (= mean of per-session k=3 deltas) + excess twin; n_sessions_used on mi_trial_animal_summaries"
    status: pending
  - id: slice_catalog
    content: "One-hold + full two-hold simple effects (genotype/sex/tx); hold_sex/hold_strain/hold_tx; min n=5/arm"
    status: pending
  - id: impl_slices
    content: "run_group_mi_tests_sliced → group_mi_sliced_tests.csv; --sliced-tests on maze-compute-stimulus-mi"
    status: pending
  - id: fdr_families
    content: "BH q_bh in families A pooled mi_mm / B slope / C career delta / D within-session delta (excess when --trial-nulls)"
    status: pending
  - id: tests_docs
    content: Synthetic 2x2x2 fixture + contract/handoff update
    status: pending
isProject: false
---

# Sliced factorial + within-session early/late (grill closed 2026-07-09)

## Goal

Conditional strata contrasts (e.g. tg vs wt within sex×tx cells) on existing animal scalars, plus within-session early−late alongside career early−late — without mixed models.

## Locked decisions

| Topic | Decision |
|-------|----------|
| Catalog | **One-hold + two-hold**; two-hold = full simple effects for genotype, sex, and tx (hold the other two at every level combo) |
| Not redundant | Two-hold adds interaction-sensitive info; nested in one-hold; smaller n; more tests |
| Cells | Primary only: `run × {duty, dist} × occupancy` |
| Min n | Both arms ≥ **5** or omit row |
| Schema | `hold_sex`, `hold_strain`, `hold_tx` (blank = not held) + `contrast_factor`, `level_a`, `level_b`, … |
| FDR | Full catalog **equal within** each family (not a tiny pre-registered subset) |
| Family A | Pooled `mi_mm` slices |
| Family B | Slope slices — **excess** if `--trial-nulls`, else raw `slope_vs_trial_ord` |
| Family C | **Career** early−late delta — excess if nulls, else raw |
| Family D | **Within-session** early−late delta — excess if nulls, else raw |
| Exploratory | Raw slope/delta when nulls on: emit `p`, **no** `q_bh` |
| Within-session δ | Per session: first/last **k=3** (need \(N_{sess}≥6\)); animal scalar = **mean** of session deltas; record `n_sessions_used` |
| Career δ | Unchanged: first/last k=3 on career `trial_ord` (all sessions on one clock) |
| CLI | `--sliced-tests` (default off); within-session columns always computed with `--per-trial` summaries |
| Output | `group_mi_sliced_tests.csv` (+ summary columns for within-session on `mi_trial_animal_summaries.csv`) |

## What MI is (for readers)

Occupancy MI is \(I(\mathrm{syll};\mathrm{stim\,bin})=D_{\mathrm{KL}}(P_{\mathrm{joint}}\|P_{\mathrm{syll}}P_{\mathrm{stim}})\), not KL between the syllable marginal and the stimulus marginal. Early/late and slopes summarize how that coupling changes over trials/sessions.

## Out of scope (explicitly deferred)

Per-session pooled MI as a first-class when-metric; rolling-block MI; \(I/H(\mathrm{stim})\) normalization; mixed-effects; claiming iti×dist sliced hits.
