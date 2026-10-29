# Uncertainty suite for composition DR

Type: research
Status: resolved
Blocked by:

## Question

For the composition-DR story (richness → entropy → dominance), which scalars are **already instrumented** on ProxComp / vault / FORMULAS, and which need a new runner before the deck can show Hill q=2 / Simpson / dominance?

Must report:

- ProxComp columns today (`dr_shannon_prox`, `dr_richness_prox`, constituents, `dr_time_prox`)
- FORMULAS / INTERPRET status of dominance / Hill q=2 (`ladder-only`?)
- Any recently synced vault estimands/runs for simpson / hill / dominance
- Recommendation: ship shannon+richness only vs extend ProxComp with λ / ¹D_q=2 before PPTX

## Answer

**Verdict:** For the sealed ProxComp composition-DR story, ship **richness + Shannon only**. Hill q=2 / Simpson dominance is already an exploratory companion in code + vault figure packs; it is **not** on the locked N=10 ProxComp board, still **`ladder-only` in FORMULAS/INTERPRET**, and must **not** gate the PPTX.

### ProxComp columns today (locked campaign root)

Path: `D:\sack\datas\impress\moseq_251017\_nor_object_mi\simpler_first_prox_comp\`  
Artifact: `prox_comp_per_animal.csv` (432 rows; INFO dated 2026-10-06). **No** `hill*` / `simpson*` / `dominance*` columns.

| Role | Columns present |
|------|-----------------|
| COUNT levels | `richness_fam_prox` / `richness_nvl_prox` (+ aliases `fam_richness_prox` / `nvl_richness_prox`) |
| UNCERTAINTY levels | `shannon_bits_fam_prox` / `shannon_bits_nvl_prox` (+ aliases `fam_shannon_prox` / `nvl_shannon_prox`) |
| DR cousins (Family A) | `dr_shannon_prox`, `dr_richness_prox` (+ `delta_*`) — finite ~403/432 |
| Time twin | `dr_time_prox` — finite ~410/432 |
| Observability | `n_frames_*_prox`, `n_spot_*_prox`, `contrast_eligible`, `min_frames_n` (=10) |

### FORMULAS / INTERPRET

- **Charted:** `richness`, `shannon_bits` ([FORMULAS.md](docs/vocab/FORMULAS.md) § COUNT/UNCERTAINTY; [INTERPRET.md](docs/vocab/INTERPRET.md) same).
- **Dominance / Hill q=2** (`λ = ∑p_k²`, `¹D_{q=2} = 1/λ`): both files still mark **`ladder-only`**. No separate Simpson-λ chart token; Hill q=2 is the named effective-number form.

### Vault (docs/vaults/moseq-fishing)

| Item | Status |
|------|--------|
| [[F ProxComp-A Score Contract]] | Family A = `dr_shannon_prox` + `dr_richness_prox` only (m=4). Documents `fam_hill2_prox` / `nvl_hill2_prox` / `dr_hill2_prox` as **exploratory companion D** — not Family A. |
| [[Run ProxComp]] | Sealed N=10 root lists shannon/richness/time only (matches on-disk CSV). |
| Companion packs (2026-10-08) | [[Run Prox Quad Comp Figs]], [[Run Prox Quad Session Step Figs]], [[Run Prox Quad Per Animal]], [[Run Prox Quad Per Model]] — emit / figure `hill2` alongside shannon/richness; vault explicitly: Family A stays shannon+richness. |
| Estimands named `simpson` / `dominance` / raw `λ` | **None** as sealed runs. Token in use is `hill2_eff` / `*_hill2_*` (= `¹D_{q=2}`). |
| On-disk hill2 outside locked root | `simpler_first_prox_comp_min0/prox_comp_per_animal.csv` has `fam_hill2_prox`, `nvl_hill2_prox`, `delta_hill2_prox`, `dr_hill2_prox` (min_frames=0). Per-model min0 consensus tables likewise. |

### Runner vs re-run (do not block PPTX)

Library path `scratch/nor_object_mi/prox_comp.py` **already emits** Hill q=2 columns. Locked `simpler_first_prox_comp/` CSV is simply **older** than that wiring. Showing hill2 on the N=10 board would be a **regen of existing runner**, not a new estimand / Family A promotion. No separate Simpson-λ runner is required (`λ = 1/hill2_eff` when finite).

### Recommendation

1. **Sealed Family A / condition lock:** shannon + richness (+ optional `dr_time_prox`) — do not promote hill2 into Family A.
2. **Deck display of dominance:** hill2 is **already available** — use `simpler_first_prox_quad_comp_figs_min0` prox panels + `prox_comp.py` / min0 CSVs. **No new runner.** (Earlier gist over-sounded like "hill2 isn't ready"; it is ready as companion figs.)
3. Vocab hygiene (optional, post-deck): FORMULAS still says `ladder-only` while min0 companions exist — promote wording later if desired.

### Correction note (2026-10-08)

User catch: hill2 artifacts live in `simpler_first_prox_quad_comp_figs_min0` (and `simpler_first_prox_comp_min0`). The Answer above already listed them; the mis-frame was ticket 04 asking to "extend the runner." Runner names for the human:

- **Scalars:** `scratch/nor_object_mi/prox_comp.py` (also driven by `simpler_first_prox_comp.py`)
- **Figs:** `scratch/nor_object_mi/fig_prox_quad_comp_violins.py` (`--kinds` includes `hill2`)

**Sources:** on-disk ProxComp CSVs; `docs/vocab/FORMULAS.md` / `INTERPRET.md`; `docs/vaults/moseq-fishing` ProxComp / Prox Quad run + score-contract notes; `scratch/nor_object_mi/prox_comp.py`.