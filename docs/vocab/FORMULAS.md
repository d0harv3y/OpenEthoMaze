# Analysis formulas

Companion to [STATS.md](STATS.md) (which tool / D vs I), [INTERPRET.md](INTERPRET.md) (what the number means), and [CONTEXT.md](CONTEXT.md) (nouns).

**Math:** KaTeX in Markdown Preview (`$…$` inline, `$$…$$` display). Preview test: [_render_test/math_preview.md](_render_test/math_preview.md). Agent chat still does not render these — keep chat answers in plain/Unicode unless the user asks for LaTeX there.

**Voice:** the equation is the thing. Accredited technique names are aliases in parentheses (and filename tokens). Discuss/plan: descriptive label first.

Notation: $p$ is one **composition** (relative shares summing to 1). Categories are taxa, functions, or syllable labels. $p_k \ge 0$, $\sum_k p_k = 1$. Frame-share in pose work: $p_k = (\text{frames labeled } k) / (\text{window frames})$. Logs are base 2 (**bits**) unless noted. **D** / **I** as in STATS.md.

charted = computed under `sack/datas/impress/moseq_251017` (mostly `_nor_object_mi/`). `ladder-only` = named on the STATS cheat sheet / crash course, not a runner in that folder.

## COUNT / UNCERTAINTY

**Category count** (D, COUNT) — charted as `richness`

$$
S = \#\{ k : p_k > 0 \}
$$

**Abundance uncertainty** (D, UNCERTAINTY) — charted as `shannon_bits`

$$
H(p) = -\sum_{k : p_k > 0} p_k \log_2(p_k)
$$

Effective number of equally abundant categories (Hill order 1): ${}^{1}D = 2^{H}$ when $H$ is in bits. Evenness is not $H$: $J = H / \log_2(S)$ when $S > 1$.

**Dominance / Hill q=2** (D, UNCERTAINTY) — `ladder-only`

$$
\lambda = \sum_k p_k^{2}, \qquad {}^{1}D_{q=2} = \frac{1}{\lambda}
$$

## Scalar rates (maze / NOR; not on the composition ladder)

**Occupancy** (D) — charted as `frac_near`

Gate is on the **bout mean** of `spot`→target distance, then occupancy is in frames:

$$
\text{near}(\text{bout}) \iff \text{bout\_mean\_dist} < r
$$

$$
\text{frac\_near} = \frac{\sum_{\text{near bouts}} \text{bout\_frames}}{\sum_{\text{all bouts}} \text{bout\_frames}}
$$

$r = 0.10\,\mathrm{m}$ in the locked NOR near / object-ball runs. `dist_any` = nearest of two targets (physical centers, or historical loci on `no_obj`). Dual-object balls: `frac_near_fam` / `frac_near_nvl` use per-object distances, not `dist_any`.

**Signed occupancy contrast** (D; then signed-rank / k-group rank = I) — charted as `DR`

$$
\mathrm{DR} = \frac{T_{\mathrm{nvl}} - T_{\mathrm{fam}}}{T_{\mathrm{nvl}} + T_{\mathrm{fam}}}
$$

Same formula, two $T$'s: investigation seconds vs object-ball occupancy frames. Exclusive form drops dual-gated frames. Undefined when both $T$'s are 0.

**Proximity preference** (D) — charted (`delta_prox`, `pref_nvl_closer`)

$$
\bar{d} = \frac{\sum (\text{bout\_mean\_dist} \times \text{bout\_frames})}{\sum \text{bout\_frames}}
$$

$$
\Delta_{\mathrm{prox}} = \bar{d}_{\mathrm{fam}} - \bar{d}_{\mathrm{nvl}}
$$

$$
\mathrm{pref} = \frac{\sum \mathbf{1}(d_{\mathrm{nvl}} < d_{\mathrm{fam}}) \times \text{bout\_frames}}{\sum \text{bout\_frames}}
$$

**Paired change** (D; then signed-rank = I) — charted

$$
\Delta_M = M_{\mathrm{right}} - M_{\mathrm{left}}
$$

Same animal; axis is condition step (`no_obj → identical → novel`) or phase step (`BL → TX → REC`). $M$ is occupancy, mean distance, category count, abundance uncertainty, or DR.

**Second-order paired change** (2×2 interaction on two axes; D — charted in `simpler_first_nested_da`) — charted

Let $M_{c,p}$ be the scalar (or $p_k$ the share) at condition level $c \in \{c_\ell, c_r\}$ and phase level $p \in \{p_\ell, p_r\}$ for **one atomic step** on each axis. First difference on condition at a fixed phase:

$$
\delta_c(p) = M_{c_r, p} - M_{c_\ell, p}
$$

Second difference across phase on that $\delta$:

$$
\Delta^2 M = \delta_c(p_r) - \delta_c(p_\ell)
= (M_{c_r, p_r} - M_{c_\ell, p_r}) - (M_{c_r, p_\ell} - M_{c_\ell, p_\ell})
$$

If you instead difference on phase first ($\delta_p(c) = M_{c, p_r} - M_{c, p_\ell}$) then across condition, expansion gives the **same four-term** sum — nesting order **commutes** for this 2×2. Same paired $n$ (all four cells). Heatmaps that facet by condition-step vs by phase-step are **transposes** of one lattice, not two estimands. k-group rank on $\Delta^2 M$ by tx (Stage B) targets the same cell either way.

## DIFFERENCE

Let $p$ and $q$ be two compositions over the same category set.

**DIFFERENCE** is the operation (“how far apart?”). Each formula below is a scalar answer. Prefer **distance** when the formula is a metric; **dissimilarity** when it may not be (esp. Bray–Curtis). Signed share change $\Delta p_k$ (DA) is a different object — see DA.

**Presence difference** (D) — Jaccard **distance** (metric on presence sets). `ladder-only` as composition distance. In DA consistency tables, the same set formula is applied to **hit-sets of ids** (see DA) — different objects.

$$
\mathrm{Jacc\_dist}(p, q) = 1 - \frac{|A \cap B|}{|A \cup B|}
$$

$A = \{k : p_k > 0\}$, $B = \{k : q_k > 0\}$.

**Abundance difference** (D) — Bray–Curtis **dissimilarity** (usually not treated as a metric). charted (SciPy `braycurtis`; paired DA uses $\mathrm{BC} = \tfrac{1}{2}\sum |p_k - q_k|$ on probability vectors, equivalent)

$$
\mathrm{BC}(p, q) = \frac{\sum_k |p_k - q_k|}{\sum_k (p_k + q_k)}
$$

On probability vectors $\sum p = \sum q = 1$, this is $\tfrac{1}{2}\sum_k |\Delta p_k|$. **Not DA** — one unsigned scalar. DA keeps the signed $\Delta p_k$.

**Phylogenetic difference** (D) — UniFrac (weighted/unweighted variants). `ladder-only`, microbiome-native. Fraction of the tree that differs. Does not transfer to syllables.

**Log-ratio difference** (D) — Aitchison **distance** (Euclidean metric after CLR). `ladder-only`

$$
d_{\mathrm{Aitch}}(p, q) = \| \mathrm{clr}(p) - \mathrm{clr}(q) \|_{2}
$$

## TRANSFORM / ORDINATE

**Log-ratio coordinates** (D, TRANSFORM) — `ladder-only`

$$
g(p) = \exp\!\left(\frac{1}{K}\sum_k \log p_k\right)
\quad\text{(geometric mean; zeros need a declared pseudocount)}
$$

$$
\mathrm{clr}(p)_k = \log\!\left(\frac{p_k}{g(p)}\right)
$$

**Feature-space projection** (D, ORDINATE) — `ladder-only`

Centered feature matrix $X$ (rows = compositions/windows). SVD / eigendecomposition of covariance; scores $= XV$. Input is features, not a distance matrix.

**Distance-space projection** (D, ORDINATE) — `ladder-only`

Input = pairwise DIFFERENCE matrix (entries may be dissimilarities or true distances — name which). Double-center the squared matrix, eigen-decompose; coordinates preserve those pairwise scalars as well as a low-rank map can. Euclidean projection after centering is close to feature-space projection — still name the input formula.

## TEST (scalars and distances)

These tests see a **scalar** (or a distance matrix), not a composition. Rank vs mean is the error model — [STATS.md](STATS.md) § Rank vs mean / [CONTEXT.md](CONTEXT.md) cousin table. We chart **rank** for NOR scalars.

**Rank (charted):** signed-rank (`wilcoxon_`, $T$); k-group rank (`kruskal_`, $H$); rank association (`spearman_`, $\rho$). Spacing discarded; order kept. These names **are** the rank procedures — not “nonparametric wrappers” around ANOVA/t.

**Mean / interval cousins (not charted as primary):** paired or two-sample t (`ttest_`, $t$); Welch t (`welch_ttest_`); classical one-way ANOVA (`anova_`, $F$); Welch / Alexander–Govern ANOVA (`welch_anova_`); Pearson (`pearson_`, $r$). Same one-factor design-strip questions as the rank side unless you move to **two-way / $k$-way** (multi-factor) models — that is a design change, not a rename of Kruskal. Never call ANOVA “parametric Kruskal” or Welch “the formal token for ANOVA.”

**Neither:** distance-matrix group partition (`permanova_`, $F$ on a DIFFERENCE matrix) uses pairwise magnitudes and a permutation null — not rank, not classical ANOVA.

### Signed-rank location (paired / vs 0)

I. charted. Alias: **Wilcoxon signed-rank**. Token: `wilcoxon_`. Statistic: $T$ (SciPy two-sided). SciPy: `stats.wilcoxon(d, alternative="two-sided", zero_method="wilcox")` (`correction=False`, `method="auto"`).

**Mean/interval cousin:** paired or one-sample $t$ (`ttest_`, statistic $t$). Not a rename of Wilcoxon.

Question: given paired differences $d_i$ (same animal, two conditions/phases, or one scalar vs 0), is the distribution of $d$ **symmetric about 0**?

That is often read as “$\mathrm{median}(d) = 0$.” That reading needs symmetry. Without it, a rejection is “signed-rank location $\ne 0$,” not automatically “median $\ne 0$.”

**Statistic** ([SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html) `wilcoxon`; source `_wilcoxon.py`)

Drop $d_i = 0$ (`zero_method="wilcox"`). Remaining count $n$. If $n < 2$ or every finite $d$ was 0 → no test.

Let $R_i$ = rank of $|d_i|$ among those $n$ (average ranks on ties). Then

$$
T^{+} = \sum_{d_i > 0} R_i, \qquad
T^{-} = \sum_{d_i < 0} R_i, \qquad
T^{+} + T^{-} = \frac{n(n+1)}{2}
$$

Two-sided `statistic` SciPy returns:

$$
T = \min(T^{+}, T^{-})
$$

One-sided `greater`/`less` instead returns $T^{+}$. (R’s `V` is $T^{+}$, not $T$ — do not match our `stat` column to R without converting.)

Descriptive companions use the **full** finite vector, zeros included: $n$, $\mathrm{median}(d)$, $\mathrm{frac}(d > 0)$. Those are D. `n_nonzero` is $n$ after the drop.

**Null mean / se of $T^{+}$** (no zeros left)

$$
\mu = \frac{n(n+1)}{4}
$$

$$
\sigma^{2} = \frac{n(n+1)(2n+1) - \tfrac{1}{2}\sum_g (t_g^{3} - t_g)}{24}
$$

$t_g$ = size of each tie group of $|d|$. Then

$$
z = \frac{T^{+} - \mu}{\sigma}
$$

Continuity (`correction=True`) moves $z$ by $0.5/\sigma$ toward 0. We leave it False.

**Two-sided p** (`method="auto"`)

SciPy first looks at the **input length** of $d$ (zeros still in): if that length $> 50$ → asymptotic. Otherwise:

- no ties and no zeros, $n \le 50$: exact null of $T^{+}$ (sign assignments equally likely);
  $$
  p = \mathrm{clip}\!\left(2 \times \min\!\big(P(T^{+} \ge \lfloor T^{+} \rfloor),\, P(T^{+} \le \lceil T^{+} \rceil)\big),\, 0,\, 1\right)
  $$
- ties or zeros, input length $\le 13$: exhaustive permutation of signs (deterministic at SciPy’s default resample cap)
- else: $p = 2\,(1 - \Phi(|z|))$ (standard normal)

Exact is only exact when there are no ties and no zeros. `stat` is not an effect size.

What this **is not**: k-group rank (`kruskal_`); two-group rank-sum (`mannwhitney_`); paired $t$; a composition test (DA applies signed-rank **per category** to $\Delta p_k$).

### k-group rank (independent groups)

I. charted (tx within sex). Alias: **Kruskal–Wallis**. Token: `kruskal_`. Statistic: $H$. SciPy: `stats.kruskal`.

**Mean/interval cousin:** classical one-way ANOVA (`anova_`, $F$) **or** Welch ANOVA / Alexander–Govern (`welch_anova_`) when variances may differ. Kruskal–Wallis is **exclusively** a rank procedure — pool values, rank, compare rank-sums. There is no parametric Kruskal–Wallis. The NOR `--stage-b anova` twin writes `welch_anova` (not Fisher `f_oneway`).

Question: do **$k$ unpaired groups** of a scalar share a distribution? Here $k = 3$ treatment arms within one sex.

Pool $N$ finite values; rank them (average ranks on ties). Group $g$ has size $n_g$ and rank-sum $R_g$.

$$
H = \frac{12}{N(N+1)}\sum_g \frac{R_g^{2}}{n_g} - 3(N+1)
$$

SciPy applies a tie correction; we store that $H$ and $p$. Under the null, $H \approx \chi^{2}$ with $(k - 1)$ df (we require $n_g \ge 2$ or skip).

Null: same distribution across groups (stochastically). Alternative: at least one group differs. A hit does **not** name the arm — read per-tx medians.

$k = 2$ is the same family as a two-sample rank-sum (`mannwhitney_`); we still run the $k$-group form because there are three txs. Cousin at $k=2$ is two-sample $t$, not ANOVA.

What this **is not**: paired signed-rank; one-way ANOVA; distance-matrix group test; a post-hoc.

**Which structure**


| Structure                                              | Rank math / token / stat     | Alias                | Mean cousin / token / stat     | Typical NOR claim                              |
| ------------------------------------------------------ | ---------------------------- | -------------------- | ------------------------------ | ---------------------------------------------- |
| same animal, two conditions/phases, or one scalar vs 0 | signed-rank · `wilcoxon_` · $T$ | Wilcoxon signed-rank | paired/one-sample t · `ttest_` · $t$ | presence/novelty Δ; phase Δ; DA Δp; DR ≠ 0     |
| different animals, tx arms, one phase/sex              | k-group rank · `kruskal_` · $H$ | Kruskal–Wallis       | one-way classical / Welch ANOVA · `anova_` / `welch_anova_` | **level:** does tx differ on raw $M$? **modulation:** Kruskal on **paired $\Delta$** by tx (`tx_on_paired_delta`) |


**Two-stage default (interaction on the move):**

1. **Stage A / first difference:** $\Delta_M = M_{\mathrm{right}} - M_{\mathrm{left}}$; signed-rank on $\Delta$ vs 0 — “did the step move $M$?”
2. **Stage B / difference-of-differences:** same $\Delta$; k-group rank on $\Delta$ across tx within sex — “did tx **modulate** that move?” (= tx × pairing **interaction** in two-way language).

Signed-rank on $\Delta$ = first difference only. k-group rank on the **same $\Delta$, split by tx** = difference-of-differences / interaction claim. k-group rank on **raw $M$** = level difference — different question. Switching to $t$ / ANOVA answers the same design strip under a different error model — rename the token.

### Distance-matrix group partition

I. charted on abundance **dissimilarity** (Bray–Curtis). Alias: PERMANOVA (Anderson 2001). Analogy-only on syllables. “Distance matrix” here means the pairwise DIFFERENCE scalar matrix — BC entries need not be metric distances.

On squared pairwise entries $d_{ij}^{2}$:

$$
\mathrm{SS}_{T} = \frac{1}{n}\sum_{i<j} d_{ij}^{2}
$$

$$
\mathrm{SS}_{W} = \sum_{\mathrm{groups}} \frac{1}{n_g}\sum_{i<j \in g} d_{ij}^{2}
$$

$$
\mathrm{SS}_{A} = \mathrm{SS}_{T} - \mathrm{SS}_{W}
$$

$$
F = \frac{\mathrm{SS}_{A}/(a-1)}{\mathrm{SS}_{W}/(n-a)}
$$

$a$ = number of groups. $p$ from permutations of labels (`n_perm = 999` in the Q2 runner):

$$
p = \frac{\#\{ F_{\mathrm{perm}} \ge F_{\mathrm{obs}} \} + 1}{n_{\mathrm{perm}} + 1}
$$

A large $F$ with a non-hit $p$ is not a claim. This tests the **distance structure**, not category count or abundance uncertainty.

## DA (differential abundance, which categories)

**Not** abundance difference (Bray–Curtis). Same L1 mass, different object.

**Paired share change** (D then signed-rank = I) — charted

$$
\Delta p_k = p_k(\mathrm{right}) - p_k(\mathrm{left})
$$

Signed-rank on $\Delta p_k$ vs 0 across animals. Shares sum to 1: one rise is another’s fall. Not ALDEx2/ANCOM. Not a distance/dissimilarity — explains one.

For syllable $k$, the **2×2 nested** $\Delta^2 p_k$ on one condition step × one phase step is the same object whether you compose condition-step then phase-step or the reverse (see **Second-order paired change** above).

**L1 contribution** (D) — charted as `bc_contrib_frac`

$$
\mathrm{bc\_contrib\_frac}_k = \frac{|\Delta p_k|}{\sum_j |\Delta p_j|}
$$

Sums to 1 when any mass moved. Not a test.

**False-discovery control** (I) — charted as `q_bh`. Alias: **Benjamini–Hochberg (BH) FDR**.

**Uncorrected** path: each test’s raw $p$ (as if alone) → companion `hit_p05` = $p < 0.05$.

**Corrected** path: adjust all finite p-values inside one **family** so the expected false-discovery *rate among the declared hits* stays controlled. Sort $p_{(1)} \le \cdots \le p_{(m)}$:

$$
q_{(i)} = \min_{j \ge i}\, \min\!\left(1,\, \frac{m\, p_{(j)}}{j}\right)
$$

Primary hit: `hit_fdr05` = $q_{\mathrm{bh}} < 0.05$. Family for DA = `model × phase × step` (finite-p syllables only). Bonferroni FWER uses $m p_{(i)}$ (chance of **any** false hit) — stricter, not what we primary. Not a bias correction of the estimator. Not an effect size.

**Volcano** (DA display) — charted. x = $\mathrm{median}(\Delta p_k)$ (effect size). y = evidence:

$$
y = -\log_{10} p
$$

Our panels clip $y$ at 4 for display. Fill = `hit_fdr05`. Overlay of models $\ne$ one BH family.

**Effect size** (D companion) — no extra formula beyond the quantity you named. For DA we report $\mathrm{median}(\Delta p_k)$ and $\mathrm{frac}(\Delta p_k > 0)$, not Cohen’s $d$. $T$, $H$, $F$, $p$, and $q$ are not effect sizes.

**Hit-set overlap** (D of I-sets) — charted. Same set formula as presence difference; **objects are FDR-hit ids** (`hit_fdr05`), not compositions.

$$
\mathrm{Jaccard}(A, B) = \frac{|A \cap B|}{|A \cup B|}
$$

Blank if both empty.

**Rank association** (I) — charted. Alias: **Spearman ρ**. Token: `spearman_`. Statistic: $\rho$.

Rank correlation of two vectors on the same units. Constant vectors → undefined.

**Mean/interval cousin:** Pearson $r$ (`pearson_`). Spearman is rank by definition — not “nonparametric Pearson.”

## INFO

**Shared information** (D estimate; permutation/group tests = I) — OEM stimulus-MI pipeline (VAST), not the NOR `moseq_251017` simpler-first folders.

$$
\begin{aligned}
I(X; Y)
  &= H(X) + H(Y) - H(X, Y) \\
  &= H(X) - H(X \mid Y) \\
  &= D_{\mathrm{KL}}\!\big(P(X,Y)\,\|\, P(X)P(Y)\big)
\end{aligned}
$$

Occupancy: $I(\mathrm{syll}; \mathrm{stim\_bin})$. Transition: $I(\mathrm{next}; \mathrm{stim} \mid \mathrm{current})$ =

$$
H(\mathrm{cur}, \mathrm{stim}) + H(\mathrm{cur}, \mathrm{next}) - H(\mathrm{cur}) - H(\mathrm{cur}, \mathrm{stim}, \mathrm{next})
$$

Finite-sample entropy bias (Miller–Madow, bits): add $(K - 1) / (2 n \ln 2)$ per entropy, with sign as in the plug-in combination (`mi_mm`). Units: bits. Shared information ≠ composition DIFFERENCE.

## VOLATILITY / MODEL

**Temporal compositional variability** (D) — `ladder-only` as a named statistic in the moseq folder. Build a time series of DIFFERENCE scalars (name distance vs dissimilarity), then summarize: mean consecutive change, variability of change, or cumulative turnover. Abundance uncertainty at each time is not volatility.

Resistance / recovery: movement during / after a perturbation — related, not synonyms.

**Trajectory class model** (I) — `ladder-only`. Alias: **LCMM**. Mixed-effects longitudinal model with latent trajectory classes. No single diversity/distance formula. Classes are model constructs.

## Composition construction (pose)

$$
p_k = \frac{\sum \text{bout\_frames on syllable } k}{\sum \text{bout\_frames in the grain}}
$$

**Bout cleanup** (optional; `_syllable_descriptives`): absorb bouts shorter than `min_bout_frames = 3` into a neighbor (bridge if labels match, else longer neighbor; tie → left). Frames are reassigned, not dropped.

## Charted in `moseq_251017`


| Family                                                                                                | Where                                                         |
| ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| category count, abundance uncertainty, abundance difference, k-group rank, distance-matrix group test | `_nor_object_mi/simpler_first_*` Q2 / near / phase-grid       |
| paired Δ, signed-rank, occupancy, `dist_any`                                                          | `simpler_first_presence_steps`, `simpler_first_phase_paired`  |
| DA Δp, FDR q, L1 contribution, hit-set overlap, rank association, volcano                             | `simpler_first_da`, phase-paired DA tables                    |
| nested $\Delta^2 p_k$ (2×2 interaction; transpose layouts b/c)                                      | `simpler_first_nested_da`                                     |
| signed occupancy contrast, object-ball occupancy                                                      | `simpler_first_object_balls_0p10`, `simpler_first_classic_dr` |
| Δ_prox, pref among frames                                                                             | Q1 / near-grain metrics                                       |
| n-gram counts (not the ladder tests)                                                                  | `_ngram_mine`                                                 |
| bout-duration descriptives                                                                            | `_syllable_descriptives`                                      |


Not charted there: log-ratio transform / difference, phylogenetic difference, feature- or distance-space projection, trajectory class models, volatility summaries, stimulus shared information (VAST kpMS MI path).
