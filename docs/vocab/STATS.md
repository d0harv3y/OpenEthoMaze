# Stats use-case cheat sheet

Curtained for **maze behavior**, **pose → syllable** pipelines, and **microbiome** collaboration. Not a general stats textbook.

**Voice:** discuss/plan uses **descriptive label first**, accredited name in parentheses. Equations (KaTeX): [FORMULAS.md](FORMULAS.md). What the number means: [INTERPRET.md](INTERPRET.md).

Nouns: [CONTEXT.md](CONTEXT.md). Crash course: https://chatgpt.com/share/6a7cf116-6b00-83e8-a963-a99662857503

## Descriptive vs inferential

**Descriptive (D)** — summarizes what is in *this* dataset: counts, rates, entropies, distances, ordination maps, trajectory summaries. No claim that a pattern would recur under resampling of the data-generating process.

**Inferential (I)** — attaches uncertainty or a decision rule to a comparison/association (p-values, intervals, model selection). Requires a stated unit of analysis (**grain**), grouping structure, and usually a null.

Rules of thumb:
- A plot or distance is **D** until a test or model says otherwise.
- Kruskal / PERMANOVA / MI tests / LCMM class inference are **I** (those names are aliases; STATS/FORMULAS lead with the operation).
- Shannon, richness, Bray–Curtis, PCA/PCoA, `frac_near` medians are **D** summaries (you may then test them — that second step is **I**).
- Never call TRANSFORM / ORDINATE / TEST / VOLATILITY / MODEL / DA “diversity metrics.”

## Rank vs mean (orthogonal to D vs I)

D vs I is the **claim**. Rank vs mean is how an **I test** treats the numeric scale — same design strip, different error model.

**Rank test:** throw away spacing; keep **order**. Named forms are rank **by definition**:
Wilcoxon signed-rank, Mann–Whitney (two-group rank-sum), Kruskal–Wallis (k-group rank), Spearman ρ.
There is **no** “parametric Kruskal” or “parametric Wilcoxon.” Switching to gaps means a **different** accredited name.

**Mean / interval cousin** (alias: **parametric**): gaps count. A Δ of 0.40 is four times a Δ of 0.10. Null is usually about **means** (or linear association for Pearson). Needs interval scale and roughly symmetric errors (or large n).

| Design strip | Rank (what we chart) | Formal / token / stat | Mean/interval cousin | Formal / token / stat |
|--------------|----------------------|-----------------------|----------------------|------------------------|
| paired Δ or one scalar vs 0 | signed-rank location | Wilcoxon signed-rank · `wilcoxon_` · $T$ | one-sample / paired t | Student’s t · `ttest_` · $t$ |
| unpaired groups ($k=2$) | two-group rank-sum | Mann–Whitney · `mannwhitney_` · $U$ | two-sample t **or** Welch t | `ttest_` / `welch_ttest_` · $t$ |
| unpaired groups ($k\ge 3$ txs) | k-group rank | Kruskal–Wallis · `kruskal_` · $H$ | classical one-way ANOVA **or** Welch ANOVA (Alexander–Govern) | `anova_` / `welch_anova_` · $F$ (or AG) |
| two vectors, same units | rank association | Spearman · `spearman_` · $\rho$ | Pearson correlation | Pearson · `pearson_` · $r$ |

**Welch ≠ “the ANOVA token.”** Welch marks **unequal-variance** mean tests. Classical one-way ANOVA assumes equal group variances. Our parametric Stage-B twin for the condition lattice uses SciPy Alexander–Govern (`welch_anova` in CSVs); CLI `--stage-b anova` is shorthand for that family, not Fisher `f_oneway`. Pairwise arms: Welch t (`welch_ttest`). Brown–Forsythe is a related unequal-variance ANOVA — not what that runner calls.

**One-way vs multiway (orthogonal to rank vs mean):**
- **One-way** — one factor (condition within a sex stratum). Default cousin to Kruskal.
- **Two-way / $k$-way** — two or more factors in one model (condition × sex, …). Same mean-scale idea; different design (main effects + interactions). Stratify-then-one-way ≠ two-way with that factor inside.
- There is no single “Kruskal two-way” that mirrors factorial ANOVA; if you need factorial structure on ranks, name the method (ART, etc.) or stay stratified.

Rules of thumb:
- Same **question shape** (e.g. “do txs differ on this scalar?”) ≠ same **procedure**. Token and statistic letter must match the procedure you ran.
- Prefer “rank test” / “mean/interval cousin” over “nonparametric” / “parametric” alone — those words get overloaded.
- We chart **rank** for NOR scalars (Δ, DR, occupancy). Mean cousins are complementary checks unless a run is explicitly the parametric twin folder.
- Distance-matrix partition (PERMANOVA) uses pairwise DIFFERENCE magnitudes with a **permutation** null — not a t-test, not a rank test, not ANOVA-on-ranks.

One- vs two-tailed is only the alternative on **the same** test, not a third family.

## Uncorrected vs multiplicity-corrected

When many tests share a **family** (e.g. one signed-rank per syllable inside `model × session × step`), each test still yields a raw **p**.

| Label | Controls | Token / flag | Role in our runs |
|-------|----------|--------------|------------------|
| **Uncorrected p** | error rate of **one** test in isolation | `p`, `hit_p05` (`p < 0.05`) | companion / exploratory |
| **FDR-corrected q** | expected fraction of **the hit list** that is false **within the family** | `q_bh`, `hit_fdr05` (`q_bh < 0.05`) | primary DA claim |
| **FWER** (Bonferroni) | chance of **any** false hit in the family | not our DA primary | stricter; different target |

**Worked FDR (the object people mix up):** you run m tests. Some are true nulls. You publish a **hit list**. FDR asks: of the things I called hits, what fraction do I expect to be duds? Target 0.05 means: if you called 20 hits in that family, expect about 1 dud **on average under the procedure** — not “each hit has p = 0.05,” and not “5 of 100 tests are false regardless of how many you called.”

Toy: 100 syllables, all truly unchanged. Uncorrected `p < 0.05` still yields ~5 accidental hits. BH raises the bar so the **list** you keep has expected dud-rate 5%. If BH leaves you 0 hits, FDR is vacuously controlled (empty list has no false discoveries).

**Uncorrected** does **not** mean wrong, unnormalized, or without bias correction (Miller–Madow on MI is a different sense of “correction”).

## Effect size vs evidence vs decision

Three different objects; volcano plots put the first two on axes and the third on fill:

| Object | Question | DA column / display | Is it “how big”? |
|--------|----------|---------------------|------------------|
| **Effect size** | how large is the move? | `median_delta_p`, `frac_gt0`, `bc_contrib_frac`; x on a volcano | yes |
| **Evidence** (uncorrected p) | how surprising under this one null? | `p`; y often −log₁₀(p) | no |
| **Decision** (FDR q / hit) | keep this id after seeing the family? | `q_bh`, `hit_fdr05`; fill on our volcanos | no |

A far-right, low point = large Δ, weak evidence. A high, near-zero point = tiny Δ, surprising (often large n). Both can be FDR-misses or hits depending on the family.

Rules of thumb:
- One planned test (e.g. one Kruskal on `frac_near` within sex) → uncorrected p is the usual decision.
- Many related tests (DA across syllables) → declare the family; prefer FDR q for the primary hit list.
- q is the **same** tests’ evidence with a different decision rule after seeing the family — not a new magnitude.
- Do not pool q-values across families (different models × phases × steps) as one leaderboard.
- Do not treat an overlay of 21 alphabets as one BH family.

## Ecology shorthand (translation only)

| Their word | Our use |
|------------|---------|
| alpha | within one composition: COUNT and/or UNCERTAINTY |
| beta | between compositions: DIFFERENCE (name which formula) |
| gamma | rare here; don’t use without defining grain |

## DIFFERENCE vs distance vs Δp

Orthogonal to D vs I. Same family, three objects:

| Object | Role | Example |
|--------|------|---------|
| **DIFFERENCE** | operation / claim: how far apart are two compositions? | “how far did left vs right shares move?” |
| **abundance difference** | one DIFFERENCE formula (abundance-sensitive scalar) | Bray–Curtis dissimilarity `BC(p, q)` |
| **dissimilarity** | scalar answer that may not be a metric | Bray–Curtis |
| **distance** | scalar answer that *is* a metric | Aitchison; Jaccard distance |
| **signed share change** $\Delta p_k$ | which categories moved | $p_k(\mathrm{right}) - p_k(\mathrm{left})$ |
| **DA** | per-category test of those $\Delta p_k$ (plus FDR) | `hit_fdr05` on syllables |

**Abundance difference vs DA (the name collision):**

| | Abundance difference | Differential abundance (DA) |
|--|----------------------|-----------------------------|
| Question | How far apart are **two whole compositions**? | **Which categories** changed share? |
| Object | **one** unsigned scalar | **K** signed $\Delta p_k$ (then I + FDR) |
| Formal / token | Bray–Curtis · `braycurtis_` | DA / `delta_p` · Wilcoxon + `q_bh` |
| D / I | D (you may then test BC) | D magnitudes + I hits |
| Algebra (probability vectors) | $\mathrm{BC} = \tfrac{1}{2}\sum_k |\Delta p_k|$ | $\Delta p_k$ is the signed piece; `bc_contrib_frac` is the share of that L1 |

Same mass, two jobs: BC folds $|\Delta p|$ into one “how far”; DA keeps the signs and tests each id. A large BC with no FDR hits is possible (mass sprinkled). FDR hits with small BC are possible (a few ids reweighted enough to surprise, little total L1).

Rules of thumb:
- Ask “are these two compositions apart?” → **DIFFERENCE** (always name the formula). Abundance-sensitive answer → Bray–Curtis, not DA.
- Ask “which syllables/taxa?” → **DA**, not BC.
- Call the formula a **distance** only when you mean the metric object (or when the literature already does).
- Prefer **dissimilarity** for Bray–Curtis when speaking strictly.
- Do not say “distance” for `Δp`, for “tx changed Shannon,” or for arena meters without saying `dist_any`.

PCoA / PERMANOVA take a matrix of pairwise DIFFERENCE scalars (often loosely called a “distance matrix” even when the entries are dissimilarities).

## Design strip: association structure

Before picking a test, name how rows relate:

| Structure | Meaning in our work | Typical move |
|-----------|---------------------|--------------|
| **Independent groups** | different animals in condition arms within one session | k-group rank (Kruskal) / distance-matrix partition (PERMANOVA) within sex |
| **Paired / repeated** | same animal across phases or times | signed-rank location (Wilcoxon); don’t treat phases as independent animals |
| **Association** | two variables on the same units (e.g. behavior ↔ composition, stimulus ↔ syllable) | MI, correlation, regression — say whether **between-animal** or **within-animal time** |
| **Compositional rows** | categories sum to a constant (relative abundances) | DIFFERENCE / TRANSFORM aware methods; DA is about categories, not Shannon |

Between-subjects association ≠ within-subject time-series dependence — name which.

## Paired change vs tx modulation (interaction / difference-of-differences)

When the same animal is measured on **left** and **right** (condition step or phase step), most NOR paired runs use **two claims** — not one omnibus test.

| Claim | Question | Object | Typical test | Token / tag |
|-------|----------|--------|--------------|-------------|
| **First difference** | Did the step move $M$ at all? | $\Delta_M = M_{\mathrm{right}} - M_{\mathrm{left}}$ per animal | signed-rank on $\Delta$ vs 0 (txs often pooled) | `wilcoxon_`; presence / phase Wilcoxon rows |
| **Difference-of-differences** | Did **condition modulate** that move? | same $\Delta$, split by condition within sex | k-group rank on $\Delta$ across condition | `kruskal_`; `condition_on_paired_delta`; Stage B |
| **Main effect of condition on level** (different!) | Are tx arms at different **levels** of $M$? | raw $M$, not $\Delta$ | k-group rank on $M$ | `kruskal_` on scalar — not the tx-on-$\Delta$ claim |

**Interaction (two-way vocabulary):** factors might be **condition** and **step** (or **session**). In a model `response ~ tx + step + tx:step`:

- **step main effect** — step matters on average (Wilcoxon on $\Delta$, pooled, is in this spirit).
- **condition main effect** — condition differs in level (Kruskal on raw $M$).
- **condition × step interaction** — the **change** depends on condition. That **is** difference-of-differences: Kruskal on $\Delta$ by condition.

We usually **do not** fit one two-way ANOVA table. Default: **stratify** (e.g. within sex), compute $\Delta$, then one-way Kruskal on $\Delta$ by condition. Same interaction-on-the-move target; declare stratum + pairing axis.

**Not** abundance difference (BC). **Not** DA (which categories). **Not** Wilcoxon alone for a treatment-modulation claim.

Examples: `simpler_first_presence_steps` (Wilcoxon then `condition_on_paired_delta`); `simpler_first_phase_paired` (`fig_phase_paired_tx_kruskal`); `simpler_first_condition_on_paired_delta` Stage A / Stage B.

### Two pairing axes (nested $\Delta$; 2×2 interaction)

Some NOR runs hold one axis fixed and pair on another **twice** — e.g. condition-step $\Delta p_k$ at each phase, then phase-step on that $\delta$ (`nested_b` / `phase_on_condition`), or the reverse (`nested_c` / `condition_on_phase`; pack `simpler_first_nested_da`).

| Question | Object | Order commutes? |
|----------|--------|-----------------|
| Does the **step on A** depend on where you are on B? | $\Delta^2 M$ on four within-animal cells (one atomic step per axis) | **Yes** — algebra is one 2×2 interaction; nesting order is a **transpose** |
| Did **condition modulate** that interaction? | same $\Delta^2 M$, k-group rank on $\Delta^2$ by condition within sex | Same cell targets (display differs) |

**Paired $n$** for a cell = animals present in **all four** endpoints. The $n$ matrix for (b) vs (c) is the same numbers **transposed** (panel titles vs column labels swap axes).

**When order would matter:** non-atomic bundles (different left→right definitions per path), different grains between stages, or nonlinear summaries — not the usual linear $\Delta p_k$ / $\Delta M$ on atomic steps.

**Not** two independent papers from two facet orders. Pick one layout for the claim; cite the other only as “same lattice, transposed.”

## Question → tool

| Question | D / I | Operation family | Formal examples (curtained) |
|----------|-------|------------------|-----------------------------|
| How many distinct categories in this composition? | D | COUNT | richness / observed |
| How uncertain is category identity in this composition *now*? | D | UNCERTAINTY | Shannon (Simpson / Hill: aliases under same family) |
| What fraction of the session is in a gated window? | D | scalar rate | `frac_near`, occupancy |
| How far apart are two compositions? | D | DIFFERENCE | Jaccard distance; Bray–Curtis (dissimilarity); UniFrac; Aitchison (distance) |
| Re-coordinate a composition for log-ratio geometry? | D | TRANSFORM | CLR (then Euclidean → Aitchison) |
| Arrange compositions from a **feature matrix**? | D | ORDINATE | **PCA** (principal components; feature-space) |
| Arrange compositions from a pairwise DIFFERENCE matrix? | D | ORDINATE | **PCoA** (principal coordinates; often fed dissimilarities) |
| Do paired scalars differ from 0 / from each other? | I | first difference | Wilcoxon on $\Delta$ (`wilcoxon_`); cousin: paired t |
| Did **condition modulate** that paired change? | I | difference-of-differences / **interaction on $\Delta$** | Kruskal on $\Delta$ by condition (`kruskal_`, `condition_on_paired_delta`); cousin: Welch ANOVA on $\Delta$ |
| Does a move on **axis A** depend on **axis B** (nested 2×2)? | D (+ I if Kruskal on $\Delta^2$ by condition) | **second-order paired change** / 2×2 interaction | nested $\Delta^2$ (`nested_da`); layouts b/c are transposes |
| Do **unpaired groups** differ on a **scalar level**? | I | k-group rank on raw $M$ | Kruskal (`kruskal_`); cousins: `anova_` / `welch_anova_` |
| Do two vectors associate monotonically? | I | rank association | Spearman (`spearman_`); cousin: Pearson (`pearson_`) |
| Do groups differ in **multivariate composition**? | I | distance-matrix group partition | PERMANOVA on a named DIFFERENCE |
| **Which categories** differ in relative use between groups? | I | category contrast / **DA** | differential abundance; contribution / SIMPER-ish — see below |
| How much does knowing Y reduce uncertainty about X? | D→I | INFO | MI (estimate is D-ish; permutation/null test is I) |
| How much does *this* composition move over time? | D | VOLATILITY | temporal compositional variability (name DIFFERENCE formula + summary) |
| Hidden trajectory subclasses over time? | I | MODEL | LCMM (classes are model constructs) |

### Differential abundance (DA)

**DA** asks: which **categories** (taxa or syllables) have different relative abundance between groups?

This is **not** abundance difference (Bray–Curtis). BC is one unsigned “how far” for the whole pair. DA is per-id signed $\Delta p_k$ + test + FDR. On probability vectors they share mass: $\mathrm{BC} = \tfrac{1}{2}\sum |\Delta p|$.

- Explains a composition **DIFFERENCE** (e.g. after Bray–Curtis PERMANOVA hits) via signed share changes — not the same object as the BC scalar.
- **Not** the same as testing richness or Shannon (those are scalar COUNT / UNCERTAINTY tests — already answered without DA).
- On syllables: label **analogy-only** unless the procedure is native to the syllable pipeline; declare grain + representation.
- Many syllables ⇒ **multiplicity**: primary hit is FDR `q_bh < 0.05` (`hit_fdr05`); uncorrected `hit_p05` is companion only. Family = the cell adjusted together (e.g. `model × session × step`).
- **Volcano** (display): x = magnitude (`median_delta_p`), y = −log₁₀(uncorrected p), fill = `hit_fdr05`. Not a new test. Overlaying models is not a joint family and not matched ids.

## Composition operations (quick ladder)

One distribution → two → groups → time → latent trajectories:

```
COUNT / UNCERTAINTY     (state of one composition)
DIFFERENCE              (how far apart are two — name distance vs dissimilarity)
TRANSFORM → ORDINATE    (re-express / map; PCA vs PCoA by input)
TEST                    (groups on scalars or DIFFERENCE matrices)
DA                      (which categories drive a DIFFERENCE via Δp)
INFO                    (shared information between variables)
VOLATILITY              (movement of one unit over time)
MODEL (LCMM)            (latent trajectory classes)
```

PCA ≠ PCoA: features in vs pairwise DIFFERENCE matrix in. Spelling is **principal**.

DIFFERENCE ≠ Δp ≠ arena `dist_*`. Volatility ≠ Shannon: movement over time ≠ state now.

Equations, SciPy notes, and `charted` vs `ladder-only`: [FORMULAS.md](FORMULAS.md). Ranges and low|zero|high: [INTERPRET.md](INTERPRET.md).

## Domain curtains

**Maze / NOR behavior** — scalars like preference, proximity, `frac_near`; grain must name `session` / `trial` / `condition` (and `interval` when used). Canonical ladder: [PROTOCOL-STRATA.md](PROTOCOL-STRATA.md).

**Pose → syllable** — compositions are **window aggregates**, not collection events. Bout ≠ window. Phylogenetic tools (UniFrac) generally do not transfer.

**Microbiome** — collection-event compositions; taxonomic vs functional **representation**; UniFrac / CLR native here. Collaborator “alpha|beta|volatility” talk maps through the table above — don’t import their pipeline into syllable code silently.

## Out of scope here

General ML, causal identification cookbooks, power-analysis encyclopedias, full GLM taxonomies, DLC/SLEAP training, DAQ/controller internals, unified NOR/VAST/RAM strata ontology (pending).
