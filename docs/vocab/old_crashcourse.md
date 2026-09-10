# Composition analysis vocabulary

Shared language for discussing compositional analyses across labs: microbiome compositions and syllable compositions. Same operations ladder; hard firewall between claims. Protocol strata (phase / session / trial / condition across NOR, VAST, RAM) are out of scope here — deferred.

Source crash course (evolving): https://chatgpt.com/share/6a7cf116-6b00-83e8-a963-a99662857503

## Voice

**Discuss / plan**: descriptive label first; formal name in parentheses.
**Implement**: formal tokens in filenames and APIs (`shannon_`, `braycurtis_`, `permanova_`, `clr_`, `pca_`, `pcoa_`, `volatility_`, `lcmm_`, …).

## Core nouns

**Composition**:
One categorical distribution over categories (taxa, functions, or syllables). Always domain-tag in prose: `microbiome composition` or `syllable composition`.
_Avoid_: bare sample (across labs), community (unless ecology interlocutor requires it)

**Representation**:
Which feature space a composition lives in. Taxonomic (organisms/ASVs) vs functional (predicted capabilities, e.g. GBM functional profiles) are parallel compositions of the same underlying community.
_Avoid_: treating “volatility” as the important word without saying *what* is changing

**Window**:
One temporal span whose frames were pooled into a syllable composition.
_Avoid_: sample, time series, epoch (NOR already uses epoch for a fixed sub-window level)

**Grain**:
The declared definition of which window (and strata) produced a composition. Required on every syllable analysis.
_Avoid_: leaving grain implicit; “the sample”

**Collection event**:
Teaching contrast only: a microbiome composition’s near-instant observational support (relative to experimental timescale).
_Avoid_: using this as syllable jargon

**Bout**:
A contiguous run of one syllable label. Not a composition unit.
_Avoid_: run (conflicts with maze `trial_state`), window, sample

## Operations ladder

Classify every named procedure by **operation**. Do not call TRANSFORM, ORDINATE, TEST, VOLATILITY, or MODEL “diversity metrics.”

**Category count** (COUNT):
How many distinct categories are present. Formal: richness / observed.
_Avoid_: diversity (alone), Shannon

**Abundance uncertainty** (UNCERTAINTY):
Entropy of one composition *at one time / one window*. Formal: Shannon.
_Avoid_: evenness (alone); “diversity metric” as a dump category; conflating with volatility

**Composition difference** (DIFFERENCE):
How far apart two compositions are. Formal aliases by retained information: Jaccard (presence), Bray–Curtis (abundance), UniFrac (phylogenetic; microbiome-only), Aitchison (log-ratio).
_Avoid_: bare “beta” without naming which difference; equating difference with mutual information or with volatility

**Log-ratio representation** (TRANSFORM):
Re-coordinates a composition for compositional geometry. Formal: CLR.
_Avoid_: calling CLR a diversity or distance measure

**Ordination** (ORDINATE):
Low-dimensional map for visualization/summary — not a DIFFERENCE definition and not a diversity metric. Two common formal tools differ by **input**:
- **Feature-space projection** — Formal: PCA (principal component analysis). Input = feature matrix (rows = compositions/windows; columns = taxa, CLR axes, syllables, …). Asks which linear combinations of features capture the most variance.
- **Distance-space projection** — Formal: PCoA (principal coordinates analysis; classical MDS). Input = pairwise distance/dissimilarity matrix already produced by DIFFERENCE. Asks whether points can sit in 2D/3D while preserving those distances.
_Avoid_: swapping PCA ↔ PCoA; “principle” (the word is **principal**); treating either as the definition of ecological/behavioral difference; calling either a diversity metric. Euclidean PCoA on distances from centered coordinates is closely related to PCA — that kinship is why the names blur; still name which input you used.

**Group separation test** (TEST):
Inferential test of between-group vs within-group difference on a distance structure. Formal: PERMANOVA.
_Avoid_: “we found diversity”; reporting a plot as a test

**Shared information** (INFO):
Expected reduction in uncertainty about one variable given another. Formal: MI (mutual information).
_Avoid_: beta diversity; “information gain” for a single observation (MI is an expectation)

**Temporal compositional variability** (VOLATILITY):
How much one subject’s composition *moves over time* (or across repeated measurements), usually summarized from a time series of DIFFERENCE values. Formal casual label: volatility. Not a single standardized statistic — always name the representation, distance, and summary (mean change / variability of change / cumulative turnover).
_Avoid_: calling volatility a kind of diversity; equating it with Shannon; bare “volatility” without *what* changed (taxonomic vs functional)

**Related trajectory notions** (not synonyms of volatility):
**Resistance** — how little composition moved during a perturbation. **Recovery / resilience** — how quickly it returned toward baseline. Separate claims from raw volatility.

**Trajectory class model** (MODEL):
Generative longitudinal model with unobserved subpopulations of trajectories. Formal: LCMM (latent class mixed model). Not a diversity metric and not a distance metric.
_Avoid_: treating latent classes as automatically real biological subtypes; equating LCMM with ordinary clustering of trajectory snapshots

## Conceptual map (one-liners)

- Shannon — how uncertain/diverse is this composition *right now*?
- Composition difference — how different are these *two* compositions?
- PCA — how do compositions arrange when I project their *feature* coordinates?
- PCoA — how do compositions arrange when I preserve their pairwise *distances*?
- Volatility — how different does *this* composition become *over time*?
- Functional volatility — how different does its *functional* representation become over time?
- MI — how much information about one variable is in another?
- LCMM — which hidden trajectory-generating classes could have produced these longitudinal observations?

## Domains

### Microbiome

**Microbiome composition**:
Composition whose categories are taxa (or ASVs/OTUs), typically one collection event per composition.
_Avoid_: silent reuse of syllable grain language

**Functional microbiome composition**:
Composition (or profile) over predicted functions rather than taxa. “GBM functional volatility” = temporal variability of that functional representation (confirm paper/software formula when citing).
_Avoid_: assuming taxonomic and functional volatility move together (functional redundancy can decouple them)

Microbiome-only difference tools (e.g. UniFrac) and compositional transforms (CLR → Aitchison) live here unless an analysis is explicitly labeled **analogy-only**.

### Syllable

**Syllable composition**:
Composition whose categories are syllable (or ethogram state) labels, obtained by pooling labeled frames over a **window**.
_Avoid_: bare sample; implying the composition is instantaneous like a microbiome collection event

Phylogenetic difference (UniFrac) generally does not transfer. CLR/Aitchison transfer only under an explicit compositional assumption and **analogy-only** labeling. Syllable “volatility” = temporal compositional variability across windows — analogy-only unless the analysis is native to the syllable pipeline; always declare grain + distance + summary.

## Firewall

**Analogy-only**:
Explicit label required when mapping a microbiome-named procedure onto syllable work (or the reverse). Must state operation + domain + grain (+ representation when taxonomic vs functional matters).
_Avoid_: “we did alpha/beta diversity” as a bridge phrase; silent transfer of UniFrac, CLR, PERMANOVA, PCA, PCoA, volatility, or LCMM claims across domains
