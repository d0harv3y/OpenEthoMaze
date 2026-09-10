# What the numbers mean

Companion to [FORMULAS.md](FORMULAS.md) (how computed), [STATS.md](STATS.md) (which claim), [CONTEXT.md](CONTEXT.md) (nouns).

**Voice:** descriptive label first; accredited names in parentheses. This file is **range and meaning**, not the equation (equations live in FORMULAS.md as KaTeX).

Inputs are always relative to a declared **grain**. A “high” Shannon on a 50-state kpMS model is not comparable to a 100-state model, or to a microbiome ASV table.

charted / `ladder-only` as in FORMULAS.md.

**I vs D:** a p-value / q-value / hit flag is a **decision under a null**, not a size. **Effect size** is the D companion (`median_delta`, `frac_gt0`, per-tx medians, the DIFFERENCE scalar itself). p answers “surprising?”; q answers “keep after the family?”; neither is how large.

**DIFFERENCE vs distance:** DIFFERENCE = the operation. The scalar answer is a **dissimilarity** (may not be a metric; Bray–Curtis) or a **distance** (metric; Aitchison, Jaccard distance). Signed `Δp_k` is neither — it is which categories moved.

## COUNT / UNCERTAINTY

**Category count** (`richness`) — D, charted

| | |
|--|--|
| Range | `0 … K` (K = alphabet size in this representation; unused ids don’t count) |
| 0 | no frames / empty composition |
| Low | few categories used in this window |
| High | many categories used (inventory, not evenness) |

Does **not** say how evenly they were used. Two windows can share S and differ totally in H.

**Abundance uncertainty** (`shannon_bits`) — D, charted

| | |
|--|--|
| Range | `0 … log2(S)` bits for this composition’s S; theoretical max `log2(K)` if every category is used and equal |
| 0 | one category has all the mass (certainty) |
| Low | peaked: a few labels dominate |
| High | flatter: a random frame is harder to guess |

Compare $H$ only at the same grain **and** similar $S$ / $K$. Rise in $H$ can be more categories **or** more evenness. Hill ${}^{1}D = 2^{H}$ is “how many equal categories would give this $H$” ($1$ = peaked, $S$ = perfectly even).

**Dominance / Hill q=2** — D, `ladder-only`

| | |
|--|--|
| $\lambda = \sum p_k^{2}$ | $(1/S) \ldots 1$ when $S$ categories used |
| $\lambda \to 1$ | one category dominates |
| $\lambda \to 1/S$ | even |
| ${}^{1}D_{q=2} = 1/\lambda$ | effective number; down-weights rares vs Shannon |

## Scalar rates (maze / NOR)

**Occupancy** (`frac_near`) — D, charted

| | |
|--|--|
| Range | `0 … 1` of session frames (bout-mean gate, then frame tally) |
| 0 | no gated-near bouts (or empty session) |
| Low | little time in the 0.10 m ball / `dist_any` window |
| High | most of the session counted near |

Not preference: high `frac_near` can be all familiar, all novel, or both. Per-object `frac_near_fam` / `frac_near_nvl` are each `0 … 1` of the **same** session denominator.

**Signed occupancy contrast** (`DR`) — D, charted

| | |
|--|--|
| Range | `−1 … +1`; **undefined** (NaN) if T_nvl = T_fam = 0 |
| −1 | all gated T on familiar |
| 0 | equal T (or exclusive overlap pulling toward 0) |
| +1 | all gated T on novel |

Small |DR| with tiny T is a noisy 0, not “no preference in a well-sampled animal.” Wilcoxon vs 0 asks location of DR, not how much time was near.

**Proximity preference** — D, charted

`Δ_prox = d̄_fam − d̄_nvl` (meters)

| | |
|--|--|
| Range | roughly `−arena … +arena`; 0 = same mean distance to both |
| > 0 | closer to novel on average |
| < 0 | closer to familiar |

`pref_nvl_closer` is `0 … 1`: frame-weighted P(d_nvl < d_fam). **0.5** is chance (not 0). 0 = always closer to familiar; 1 = always closer to novel.

**Paired change** `Δ_M = M_right − M_left` — D, charted

| | |
|--|--|
| Range | same units as M; 0 = no change on that animal |
| Sign | + = right larger than left (e.g. occupancy went up after objects appeared) |
| Magnitude | comparable only for the same M and grain |

Median(Δ) and `frac(Δ > 0)` are the D story; signed-rank p is not.

**Tx modulation on Δ** (difference-of-differences / interaction on the move) — I, charted

Same $\Delta_M$ as above; claim is **not** “did the step move?” but “did **tx** change how much animals moved?”

| | |
|--|--|
| Object | one $\Delta$ per animal, compared across condition arms within sex |
| Test | k-group rank on $\Delta$ (`kruskal_`; tags `condition_on_paired_delta`, Stage B) |
| Hit | usually uncorrected `p < 0.05` on that Kruskal cell (not DA FDR) |
| Read with | per-tx medians of $\Delta$ — Kruskal does not name the winning arm |

**Not** Wilcoxon on $\Delta$ (first difference, txs pooled). **Not** Kruskal on raw $M$ (level main effect). **Not** BC or DA. In two-way language: **tx × pairing interaction** on the change score; our runs often implement it as stratify → $\Delta$ → Kruskal, not one factorial table.

**Nested $\Delta$ on two axes** (2×2 interaction) — D then optional Kruskal on $\Delta^2$ by condition — charted

| | |
|--|--|
| Object | one $\Delta^2 M$ (or $\Delta^2 p_k$) per animal per **(condition step × phase step)** cell |
| First stage | two within-animal differences on a 2×2 of endpoints |
| Read | “does the move on axis A **depend on** where you are on axis B?” |
| Layout | facet by condition step **or** by phase step — **same numbers**, transposed panels |
| Paired $n$ | animals in **all four** cells; identical whether you nest A→B or B→A |
| Avoid | publishing (b) and (c) as two separate findings |

Example pack: `simpler_first_nested_da` (`fig_nested_b_*` vs `fig_nested_c_*`). Stage B Kruskal on $\Delta^2$ by condition is still **tx modulation on the interaction**, not a third nesting order.

## DIFFERENCE

All of these are scalar answers to “how far apart are two compositions?” 0 = identical on that definition. They are not “diversity.” Call the scalar a **distance** only when it is a metric; otherwise **dissimilarity**.

**Presence difference** (Jaccard **distance**) — D, `ladder-only`

| | |
|--|--|
| Range | `0 … 1` |
| 0 | same presence set |
| 1 | no shared categories |

Ignores abundance. Metric on presence sets. **Hit-set Jaccard** (DA consistency) uses the same formula on **id sets**; 1 = identical hit lists, 0 = disjoint. Blank if both sets empty (undefined, not 0).

**Abundance difference** (Bray–Curtis **dissimilarity**) — D, charted

| | |
|--|--|
| Range | `0 … 1` for nonnegative compositions |
| 0 | same relative abundances |
| 1 | no mass in common (disjoint support, or one empty vs one not) |

On probability vectors, $\mathrm{BC} = \tfrac{1}{2}\sum |p - q| = \tfrac{1}{2}\sum |\Delta p|$. Prefer “dissimilarity” over “distance” when strict. A large paired BC says the animal’s **whole** share vector moved a lot. It does **not** name which syllables — that is **DA** (signed $\Delta p_k$, L1 contribution, volcano). Testing BC (Wilcoxon / PERMANOVA) is still a DIFFERENCE test, not DA.

**Phylogenetic difference** (UniFrac) — D, `ladder-only`, microbiome

| | |
|--|--|
| Range | typically `0 … 1` (variant-dependent) |
| 0 | same tree occupancy |
| High | mass/presence on distant clades |

Not a syllable quantity. Say “UniFrac” rather than bare “distance.”

**Log-ratio difference** (Aitchison **distance**) — D, `ladder-only`

| | |
|--|--|
| Range | `0 … ∞` (Euclidean on CLR) |
| 0 | same log-ratio structure (after the declared zero handling) |
| High | ratios among categories changed a lot |

True metric after CLR. Not interchangeable with Bray–Curtis: doubling all abundances (if you had counts) can look small in log-ratio space and large in L1.

## TRANSFORM / ORDINATE

**Log-ratio coordinates** (CLR) — D, `ladder-only`

Each coordinate is $\log(p_k / g(p))$. Unbounded; $\sum_k \mathrm{clr}_k = 0$. Positive = above geometric-mean share; negative = below. Not a distance until you take Euclidean (Aitchison). Zeros need a declared pseudocount — that choice moves every coordinate.

**Feature-space projection** (PCA) — D, `ladder-only`

Scores have **no universal units**. Axis 1 is “direction of most variance in this matrix,” not a biological axis. Distance on the plot is not Bray–Curtis unless you put BC in and used distance-space projection.

**Distance-space projection** (PCoA) — D, `ladder-only`

Points close ⇒ small pairwise DIFFERENCE scalar **in the matrix you fed it** (dissimilarity or distance — name which). Stress / leftover eigenvalues: the 2D map is incomplete. The plot is D; group separation on the plot is not a test.

## TEST (do not read as effect size)

**Effect size** = how large the move is on the declared scale. p / q / hits are not that. Rank tests (what we chart) further ignore spacing when *testing*; they still have a D companion (median Δ, `frac_gt0`) for size. A mean/interval cousin (t, ANOVA, Pearson) would let a Δ of 0.40 outweigh 0.10 **inside the test**. Same p-rule either way: p is not magnitude. Cousin table: [STATS.md](STATS.md) § Rank vs mean / [CONTEXT.md](CONTEXT.md).

Rank procedures are rank **by name** (`wilcoxon_`, `kruskal_`, `mannwhitney_`, `spearman_`). Switching to gaps requires a **different** token (`ttest_`, `anova_`, `pearson_`) — never “parametric Wilcoxon/Kruskal.”

**p-value** (signed-rank, k-group rank, distance-matrix partition, Spearman, …) — I

| | |
|--|--|
| Range | `(0, 1]` in practice; never a magnitude |
| Near 0 | data this extreme (or more) would be rare **under the stated null** |
| Near 1 | typical under that null |

**Uncorrected** (`p`, `hit_p05`): treat this test in isolation; hit usually `p < 0.05`. Fine when the test was planned alone (one Kruskal, one Wilcoxon on DR).

**Multiplicity-corrected** (`q_bh`, `hit_fdr05`): after many related tests in one **family**, BH FDR q; primary DA hit `q_bh < 0.05`. Same underlying tests; different decision rule. q is not effect size and is not comparable across families.

A tiny p with a tiny median Δ is still a small move. A large $F$ / $H$ with p = 0.3 is **not** a hit. Do not compare $H$ to ANOVA’s $F$ as if they were the same statistic.

**Signed-rank statistic $T$** (Wilcoxon; token `wilcoxon_`) — I companion, charted

| | |
|--|--|
| Range | `0 … n(n+1)/4` because $T = \min(T^{+}, T^{-})$ |
| $T$ near 0 | one sign’s ranks dominate (strong imbalance) |
| $T$ near the max | $T^{+} \approx T^{-}$ (balanced ranks) |

Do not compare $T$ across different $n$. R’s $V$ is $T^{+}$, not $T$. **Cousin:** paired/one-sample $t$ (`ttest_`) — different letter, different token.

**k-group $H$** (Kruskal–Wallis; token `kruskal_`) — I, charted

| | |
|--|--|
| Range | $\ge 0$; large under the $\chi^{2}(k-1)$ picture |
| 0 | identical rank mixes across groups |
| High | groups occupy different rank regions |

Does not say which tx or which way — read `median_noSD` / `median_GHSD` / `median_RBSD`. **Exclusively** a rank test (pool → rank → $H$). **Cousins:** classical one-way ANOVA (`anova_`, $F$) or Welch / Alexander–Govern (`welch_anova_`) — not a rename of Kruskal. Two-way / $k$-way ANOVA is a **different design** (multiple factors), not the default Kruskal twin.

**Distance-matrix $F$** (PERMANOVA; token `permanova_`) — I, charted

| | |
|--|--|
| Range | `≥ 0` (∞ if within-group SS is 0) |
| Near 0 | between-group SS small vs within |
| High | between-group distances large **relative to** within-group |

p from permutations. BL/TX in our NOR tables can show large F with non-hit p — **F is not the claim**. Analogy-only on syllables.

## DA

**Not** abundance difference. Abundance difference = one Bray–Curtis scalar for the pair. DA = which ids, which way.

**Paired share change** $\Delta p_k$ — D, charted

| | |
|--|--|
| Range | $-1 \ldots +1$; $\sum_k \Delta p_k = 0$ (shares) |
| 0 | that syllable’s frame-share unchanged |
| + | higher share on the right condition/phase |
| − | lower share on the right |

A $+$ on one id **requires** $-$ elsewhere. Median $\Delta p$ is D; signed-rank $p$ / $q$ is I. **Not** a Bray–Curtis / distance — it is the per-category signed change that can *explain* an abundance dissimilarity.

**L1 contribution** (`bc_contrib_frac`) — D, charted

| | |
|--|--|
| Range | `0 … 1`; sums to 1 when any mass moved |
| 0 | this id didn’t move (or compositions identical) |
| High | this id is a large slice of $\sum |\Delta p|$ |

Not a test. A high contribution can be a common syllable twitching or a rare one flipping.

**FDR q** (`q_bh`) — I, charted (multiplicity-corrected)

| | |
|--|--|
| Range | $0 \ldots 1$ |
| Low | this test survives within-family false-discovery control |
| $q < 0.05$ | our primary DA hit (`hit_fdr05`) |

Read as: “if I keep every id with $q$ below this cutoff **in this family**, I expect about 5% of **that list** to be false.” Not “this syllable has a 5% chance of being fake” in isolation. Not Bonferroni (chance of **any** false hit). Not effect size. Family is `model × session × step` (or the analogous cell). **Uncorrected** companion: `hit_p05` on raw `p`. q is **not** comparable across families as a single ranking of biology. Empty hit list ⇒ FDR is controlled (no discoveries to be false). “Uncorrected” ≠ unnormalized ≠ Miller–Madow bias correction.

**Volcano plot** — DA display, charted (`fig_da_volcano_*`)

One point = one `model × syllable` in one phase × step panel. Not a new statistic.

| Axis / mark | Encodes | Low / left | High / right or up |
|-------------|---------|------------|-------------------|
| x | effect size: `median_delta_p` | more share on the left condition | more share on the right |
| y | evidence: $-\log_{10} p$ (uncorrected), display-clipped at 4 | unsurprising | surprising under that one null |
| fill | decision: `hit_fdr05` | open = miss | filled = BH hit **inside that cell** |
| color | alphabet size $K$ (`ss-50` vs `ss-100`) | — | not a shared syllable id |

Two panels (presence vs novelty). Shared x-limits across phase stems so Δp scale is comparable. Overlaying 21 models is a **display**; BH is still per `model × session × step`. Height is not size. A tall near-zero spike is a tiny Δ with strong evidence. A far, short point is a large Δ that did not surprise the signed-rank.

**Rank association** (Spearman $\rho$; token `spearman_`) — I, charted

| | |
|--|--|
| Range | $-1 \ldots +1$; NaN if a vector is constant or $n < 3$ |
| 0 | no monotonic rank agreement |
| $+1$ / $-1$ | ranks identical / reversed |

Association of **ranks**, not of the raw $\Delta p$ scale. **Cousin:** Pearson $r$ (`pearson_`) on the raw scale — different token.

## INFO / VOLATILITY / MODEL

**Shared information** $I(X; Y)$ — D estimate (bits), `ladder-only` in moseq_251017 (VAST MI path)

| | |
|--|--|
| Range | $0 \ldots \min(H(X), H(Y))$ |
| 0 | independent (plug-in can be slightly off-zero) |
| High | knowing one shrinks uncertainty in the other a lot |

Not a composition distance. Occupancy vs transition are different questions. Miller–Madow `mi_mm` is a bias-adjusted estimate, still D until you test it.

**Temporal compositional variability** — D, `ladder-only`

Meaning follows the **named distance + summary** (mean consecutive BC ≠ cumulative turnover). High = the unit’s composition moved a lot over time. Independent of Shannon-at-each-time (state now vs movement).

**Trajectory class model** (LCMM) — I, `ladder-only`

Class index is a **model construct**, not a verified subtype. Posterior probability near 1 = the model is sure of its assignment, not that biology has two kinds of mouse.

## Pose construction

**Frame-share** $p_k$ — D: $0 \ldots 1$, $\sum p = 1$. 0 = unused in this grain. High = that label occupies the window.

**Bout cleanup** does not drop frames; short bouts get a neighbor’s label. Inventory S can fall; total frames stay put.
