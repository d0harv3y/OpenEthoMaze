# Analysis vocabulary

Canonical nouns for maze / pose·syllable / microbiome analyses. For **which tool for which claim**, see [STATS.md](STATS.md). Equations (KaTeX): [FORMULAS.md](FORMULAS.md). Ranges / low–zero–high: [INTERPRET.md](INTERPRET.md). Protocol ladder (`session` / `trial` / `interval`) and animal strata (`condition`, …): [PROTOCOL-STRATA.md](PROTOCOL-STRATA.md).

## Voice

**Discuss / plan**: descriptive label first; formal name in parentheses.
**Implement**: formal tokens in filenames and APIs (`shannon_`, `H_next_given_curr`, `trans_dist_to_nosd_ref`, `resid_`, `braycurtis_`, `wilcoxon_`, `kruskal_`, `spearman_`, `permanova_`, `anova_`, `ttest_`, `clr_`, `pca_`, `pcoa_`, `volatility_`, `kaplan_meier_`, `logrank_`, …).

## Language

**Composition**:
One categorical distribution over categories (taxa, functions, or syllables). Always domain-tag: `microbiome composition` or `syllable composition`.
_Avoid_: bare sample (across labs), community (unless an ecology interlocutor requires it)

**Representation**:
Which feature space a composition lives in (taxonomic vs functional vs syllable labels). Parallel representations of the same underlying process are allowed; name which one you used.
_Avoid_: reporting “volatility” or “difference” without saying *what* representation changed

**Window**:
One temporal span whose frames were pooled into a syllable composition.
_Avoid_: sample, time series, epoch (NOR already uses epoch for a fixed sub-window level)

**Grain**:
The declared definition of which window and strata produced a unit of analysis. Required on every syllable (and preferred on every maze) analysis.
_Avoid_: leaving grain implicit; “the sample”

**Collection event**:
Teaching contrast only: a microbiome composition’s near-instant observational support (relative to experimental timescale).
_Avoid_: using this as syllable jargon

**Bout**:
A contiguous run of one syllable label. Not a composition unit and not a grain.
_Avoid_: run (conflicts with maze `trial_state`), window, sample

**Entropy (Shannon; marginal)** (operation UNCERTAINTY; token `shannon_` / `shannon_bits`):
Average uncertainty (bits) about **which category** under **one** composition $p$ at one grain — formal $H(p)$. In our vocab **entropy = uncertainty** for a declared categorical law. Distinct from sample **variance**; from **conditional entropy** $H(Y \mid X)$; from **MI** (shared information).
_Avoid_: “entropy changed” without naming occupancy $p$ vs transition $P$; calling every $H$ Shannon-on-$p$

**Conditional entropy** ($H(Y \mid X)$; UNCERTAINTY):
Uncertainty left in $Y$ after knowing $X$. Canonical bout form: $H(\mathrm{next} \mid \mathrm{current})$ (`H_next_given_curr`) from row-stochastic $P(\mathrm{next} \mid \mathrm{current})$. Related: $I(X;Y) = H(Y) - H(Y \mid X)$.
_Avoid_: equating with marginal Shannon on window $p$; equating with $I(\mathrm{next};\mathrm{stim}\mid\mathrm{current})$; calling Miller–Madow “conditional entropy”

**Total variation (TV) distance** (DIFFERENCE between two laws on the same support; token `trans_dist_to_nosd_ref`):
How far apart are two **transition matrices** $P$ and $Q$? $\mathrm{TV}=\tfrac{1}{2}\sum_{i,j}|P_{ij}-Q_{ij}|$. Name is **total variation**, not **total variance** ($\sigma^2$). Charted vs a pooled reference law.
_Avoid_: “TV” for ANOVA variance components; reading animal TV without transition-count checks (sparse → uniform $P$ → inflated TV)

**Transition** (bout-to-bout; operation TRANSITION):
How the **next** bout label depends on the **current** one. Core objects: $P(\mathrm{next} \mid \mathrm{current})$; $H(\mathrm{next} \mid \mathrm{current})$; optional TV of $P$ to a reference; pair MI / bigram richness at a fixed transition budget. Built on the **bout stream**, not on a window composition. See [FORMULAS.md](FORMULAS.md) § TRANSITION.
_Avoid_: calling Shannon-on-$p$ a transition summary; equating $H(\mathrm{next}\mid\mathrm{current})$ with occupancy MI or $I(\mathrm{next};\mathrm{stim}\mid\mathrm{current})$; reading TV without a transition-count check (sparse → nearer-uniform $P$ → larger TV)

**Microbiome composition**:
Composition over taxa (or ASVs/OTUs), typically one collection event per composition.
_Avoid_: silent reuse of syllable grain language

**Functional microbiome composition**:
Composition (or profile) over predicted functions rather than taxa.
_Avoid_: assuming taxonomic and functional summaries move together (functional redundancy can decouple them)

**Syllable composition**:
Composition over syllable (or ethogram state) labels, obtained by pooling labeled frames over a **window**.
_Avoid_: implying the composition is instantaneous like a microbiome collection event

**Analogy-only**:
Explicit label when mapping a microbiome-named procedure onto syllable/maze work (or the reverse). Must state operation + domain + grain (+ representation when it matters).
_Avoid_: “we did alpha/beta diversity” as a bridge phrase; silent transfer of UniFrac, CLR, PERMANOVA, PCA, PCoA, volatility, LCMM, or differential abundance claims across domains

**Composition difference** (operation DIFFERENCE):
The claim “how far apart are these two compositions?” Named formulas (Jaccard, Bray–Curtis, UniFrac, Aitchison) answer it.
_Avoid_: bare “difference” without naming the formula; calling Δp or a Shannon change “a distance”

**Dissimilarity**:
A scalar “how far” `d(p, q)` under DIFFERENCE that may fail metric axioms (especially the triangle inequality). Prefer this word for Bray–Curtis when speaking strictly.
_Avoid_: calling every DIFFERENCE formula a “distance”

**Distance** (metric sense):
A scalar `d(p, q)` that is a true metric (nonnegative, identity, symmetry, triangle inequality). Aitchison and Jaccard distance qualify; Bray–Curtis usually does not.
_Avoid_: “distance” for signed category changes (Δp) or for arena meters (`dist_any`) without context

**Abundance difference** (DIFFERENCE scalar; token `braycurtis_`):
One number: how far apart are two compositions **on relative abundances**? Formal: Bray–Curtis **dissimilarity**. Unsigned. Does not name which categories moved.
_Avoid_: calling this “DA”; calling BC “differential abundance”

**Differential abundance (DA)**:
Which **categories** changed relative use (signed `Δp_k` per id, then a test + FDR). Explains an abundance difference; is not the BC scalar. L1 contribution (`bc_contrib_frac`) slices the same unsigned mass that BC folds up.
_Avoid_: calling median `Δp` “the Bray–Curtis”; calling a BC Wilcoxon “DA”

**Signed share change** ($\Delta p_k$ / token `delta_p`):
Per-category $p_k(\mathrm{right}) - p_k(\mathrm{left})$. The DA magnitude object. Not itself a distance/dissimilarity.
_Avoid_: calling $\Delta p$ “the Bray–Curtis”

**Volatility** (temporal compositional variability; token `volatility_`; operation VOLATILITY):
How much **one** unit’s composition **moves over time** (or across repeated windows), usually from a time series of DIFFERENCE scalars. Always name representation + DIFFERENCE formula + summary (mean consecutive change / variability of change / cumulative turnover). `ladder-only` in `moseq_251017` simpler-first (not charted there). Syllable use is **analogy-only** unless a native pipeline declares grain + distance + summary.
_Avoid_: calling volatility a diversity metric; equating it with Shannon (state now ≠ movement); bare “volatility” without *what* representation moved; treating one paired BC as “volatility”

**Related trajectory notions** (not synonyms of volatility):
**Resistance** — how little composition moved **during** a perturbation. **Recovery / resilience** — how quickly it returned toward baseline. Separate claims from raw volatility.

**Residual** (model leftover; token `resid_*`; operation RESIDUAL):
What remains of an observed scalar $y$ after subtracting a fitted prediction $\hat y$ from declared covariates: $e = y - \hat y$. In NOR residual litmus: OLS within sex of syllable scalars (Shannon, $H(\mathrm{next}\mid\mathrm{current})$, pair MI) on Layer A locomotor / proximity covariates (`mean_speed_mps`, `frac_still`, `frac_near_nvl`), then Kruskal on `resid_*` by `condition`. Declare $Y$, $X$s, stratum, and fit. Residual is D of the leftover; testing residuals by groups is I.
_Avoid_: equating with **conditional entropy** $H(Y \mid X)$ (information leftover, not regression leftover); calling FDR / Miller–Madow a residual; bare “residual” without naming outcome and covariates

**Rank test**:
Inferential comparison that uses only the **order** of values (signed-rank, two-group rank-sum, k-group rank, Spearman). Spacing discarded. Named procedures (**Wilcoxon signed-rank**, **Mann–Whitney**, **Kruskal–Wallis**, **Spearman**) are **rank by definition** — there is no “parametric Kruskal” or “parametric Wilcoxon.”
_Avoid_: nonparametric (overloaded); calling Shannon or Bray–Curtis “rank tests”; “parametric Kruskal–Wallis”

**Mean / interval cousin** (alias: **parametric**):
Same **design strip** as a rank test, but gaps count (t-test, ANOVA, Pearson). Different named procedure, different statistic letter, different filename token.
_Avoid_: treating t vs Wilcoxon as different *questions*; renaming ANOVA as “parametric Kruskal”

| Design strip | Rank (what we chart) | Token / stat | Mean/interval cousin | Token / stat |
|--------------|----------------------|--------------|----------------------|--------------|
| paired Δ or scalar vs 0 | signed-rank | `wilcoxon_` / $T$ | paired / one-sample t | `ttest_` / $t$ |
| unpaired $k=2$ | two-group rank-sum | `mannwhitney_` / $U$ | two-sample t (equal-var) or **Welch t** | `ttest_` / `welch_ttest_` / $t$ |
| unpaired $k\ge 3$ | k-group rank | `kruskal_` / $H$ | **classical** one-way ANOVA or **Welch ANOVA** (e.g. Alexander–Govern) | `anova_` / `welch_anova_` / $F$ (or AG statistic) |
| association of two vectors | rank association | `spearman_` / $\rho$ | Pearson correlation | `pearson_` / $r$ |

**Welch** is **not** a synonym for ANOVA/t. It names the **unequal-variance** mean-scale variant (Welch t for $k=2$; Welch / Alexander–Govern ANOVA for $k\ge 3$). Classical one-way ANOVA (`f_oneway`) assumes equal variances. CLI shorthand `--stage-b anova` in the NOR tx lattice currently means Welch ANOVA in the CSV (`test=welch_anova`) — say so; do not pretend it is Fisher `f_oneway`.

**One-way vs two-way vs $k$-way** (orthogonal to rank vs mean):
- **One-way:** one factor (e.g. condition within a sex stratum). What our cousin table means by default.
- **Two-way / $k$-way (multiway):** two or more factors in one model (e.g. condition × sex, or condition × session). Same mean-scale family; different **design strip** (interactions, main effects). Not “parametric Kruskal.” Stratifying by sex then running one-way ≠ putting sex in a two-way model.
- Rank side has no single Kruskal analogue for full factorial designs; people use aligned-rank / ART / separate strata — name what you did.
_Avoid_: calling every mean-scale k-group test “ANOVA” without one-way vs multiway and classical vs Welch

**k-group vs k-way vs k-ary** (do not synonymize):

| Term | Counts | Our use |
|------|--------|---------|
| **k-group** | levels of **one** factor (how many arms) | Kruskal / one-way ANOVA among $k$ txs (`kruskal_`, `anova_`) |
| **k-way** | how many **factors** in one model | two-way = condition × sex; three-way = three factors |
| **k-ary** | arity of a relation/operator (CS/math; sometimes ML class count) | **not** our stats jargon — do not say “k-ary Kruskal” or “k-ary ANOVA” |

Trap: “three-group Kruskal” = k-group with $k=3$. “Three-way ANOVA” = three **factors**. Different claims.
_Avoid_: k-ary as a stand-in for k-group or k-way

**First difference** (paired change; token `delta_*`):
Within one animal (or one pairing axis), $\Delta_M = M_{\mathrm{right}} - M_{\mathrm{left}}$. Answers: “did this step move $M$?” Test: signed-rank on $\Delta$ vs 0 (`wilcoxon_`), often txs pooled.
_Avoid_: calling this an interaction; calling Kruskal on raw $M$ the same claim

**Difference-of-differences** (tx modulation on $\Delta$; token `condition_on_paired_delta`, Stage B):
Same $\Delta$ per animal, then compare **distributions of $\Delta$** across condition arms within sex. Answers: “did treatment **modulate the move**?” Test: k-group rank on $\Delta$ by condition (`kruskal_`). Alias in econometrics: difference-in-differences (DiD) on the change score.
_Avoid_: “tx changed $M$” when you mean “tx changed **how much** $M$ moved”; pooling this with Wilcoxon on $\Delta$

**Interaction claim** (factor × pairing):
In a two-way picture (e.g. condition × step), the **interaction** is “does the **effect of the step** depend on tx?” Same object as difference-of-differences on $\Delta$. **Main effect of step** ≈ Wilcoxon on $\Delta$ (pooled). **Main effect of condition on level** ≈ Kruskal on raw $M$, not on $\Delta$. Our default is **two-stage** (form $\Delta$, then Kruskal by condition within stratum), not one full factorial table — still an interaction-on-the-move claim.
_Avoid_: “interaction” for any Kruskal; stratify-then-one-way without saying which factor is the pairing axis

**Nested pairing on two axes** (2×2 interaction on the move; token `nested_da`, `Δ²`):
When an animal has $M$ (or $p_k$) at **four cells** — left/right on **axis A** × left/right on **axis B** (e.g. one condition step × one phase step) — you can form a **first difference** on A at each level of B, then a **second difference** across B on that $\delta$. Or the reverse: first difference on B at each level of A, then across A. For **atomic** steps (one left→right pair per axis), both orders yield the **same** $\Delta^2 M$ per animal and the **same** paired $n$ (intersection of all four cells). Faceting by A vs by B is a **layout transpose**, not a second estimand.
_Avoid_: treating “condition first, then phase” and “phase first, then condition” as two biology claims; double-reporting both heatmaps as independent findings

**Uncorrected p** (`p`, companion flag `hit_p05`):
The raw p-value from one test, as if that test were the only one. Answers: “under this null, how surprising is *this* result?”
_Avoid_: “uncorrected” for bias adjustments (e.g. Miller–Madow on MI) or for unnormalized data

**Multiplicity correction**:
Adjusting many related p-values so the chance of false claims does not grow with the number of tests. Requires a declared **family** (the set of tests adjusted together).
_Avoid_: applying a family correction without naming the family; treating corrected q as a different test of a new hypothesis

**FDR q** (`q_bh`, primary DA flag `hit_fdr05`):
Benjamini–Hochberg (BH) **false-discovery rate** control within one family. If you declare a hit list, FDR is the expected fraction of **those hits** that are false. q is not “wrong p” and not a size; it is a decision threshold after seeing the whole family.
_Avoid_: comparing q across families as one ranking of biology; calling FDR “Bonferroni” (that is family-wise error: chance of **any** false hit); treating q as effect size

**Family-wise error (FWER)** (Bonferroni and cousins):
Chance of **at least one** false hit in the family. Stricter than FDR when m is large. We do not use it as the DA primary.
_Avoid_: saying “FDR is Bonferroni”

**Tukey’s HSD** (Honest Significant Difference; “Tukey adjustment”):
Post-hoc **pairwise mean** comparisons after classical one-way ANOVA among $k$ groups. Controls FWER for **all pairs** in that $k$-group family (not FDR; not Bonferroni on an arbitrary list). Token if needed: `tukey_`. Classical equal-variance mean procedure — not the default after Kruskal or Welch/Alexander–Govern.
_Avoid_: calling BH “Tukey”; using Tukey after Kruskal (rank post-hocs are Dunn / Conover and cousins); treating Tukey as our DA primary or as Stage-B omnibus

**Effect size** (magnitude; D companion to an I test):
How **large** the move is on the declared scale — not how surprising. In our DA tables: `median_delta_p`, `frac_gt0`, `bc_contrib_frac`. Elsewhere: paired Δ, DR, occupancy, BC. p and q are **not** effect sizes (tiny p can sit on a tiny Δ if n is large).
_Avoid_: reading −log₁₀(p) or q as “how big”; calling T / H / F an effect size without conversion

**Volcano plot** (DA display):
Scatter of **magnitude** (x, usually `median_delta_p`) vs **evidence** (y, usually −log₁₀ of uncorrected p). Fill/color often marks FDR hits. Overlaying models is a display choice, not a joint BH family.
_Avoid_: reading height as size; pooling overlay points as one FDR family; treating color as a shared syllable id across alphabets

**Time-to-event** (latency with incomplete follow-up):
How long until a **named event** (first baited-arm entry, first error, trial complete, first near-bout, …). Units that never fire the event before observation ends are **right-censored**, not “event at session end” and not dropped. Grain must name the clock (trial / session) and the event.
_Avoid_: treating never-happened as missing, as 0, or as max trial duration without declaring censoring

**Kaplan–Meier estimator** (token `kaplan_meier_`; operation TIME-TO-EVENT):
Nonparametric **survival** curve: share of units that have **not yet had the event** by time $t$, using right-censored rows. Step function; D of this sample. `ladder-only` until a runner exists. Natural maze home: **RAM** (radial-arm maze) latencies; also NOR/VAST first-contact clocks when censoring is real.
_Avoid_: calling occupancy / `frac_near` a KM; equating KM with volatility; reporting mean latency that ignores censoring

**Log-rank** (token `logrank_`):
Inferential cousin: do two (or k) KM curves differ? I. Not an effect size; median time-to-event (when $\hat S$ crosses 0.5) is the D magnitude companion.
_Avoid_: calling log-rank a Kruskal on raw latencies (that discards censoring)

## Protocol strata (pointer)

Wire ladder and animal strata live in [PROTOCOL-STRATA.md](PROTOCOL-STRATA.md). Do not invent a second hierarchy here; do not use `phase` / `stage` / `tx` as column names in new work.
