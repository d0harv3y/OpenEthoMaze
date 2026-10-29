# Build missing join boards

Type: task
Status: resolved
Blocked by: 04, 05, 06

## Question

(Unblocking task, not a science decision.) Produce INFO + figures for the locked contracts.

### Must build (exemplar `paramscan_s1-1e7_s2-3e4_ss-100`)

| ID | Deliverable |
|----|-------------|
| A | classic DR ↔ `dr_time_prox` scatter + Spearman @ `NOR_TX` × `nvl_obj` |
| C | `frac_still` ↔ syll5 **level** frame-share (animal × session × trial) |
| D | classic DR ↔ `dr_shannon_prox` / `dr_richness_prox` / `dr_hill2_prox` (v1) |
| E | ProxComp level/DR violins + condition Kruskal for shannon/richness/hill2 on **exemplar raw alphabet** (not cluster) |
| F | Session-step prox shannon/richness/hill2 boards on **exemplar** (not cluster) |

### Reuse

| ID | Artifact |
|----|----------|
| B | `fig_classic_vs_object_prox` |
| G | one `session_paired` time/occupancy Δ twin |

### Done when

Runners under `scratch/nor_object_mi/`; arts under sack `_nor_object_mi/`; vault Run notes in `docs/vaults/moseq-fishing/`. PPT assembly is ticket 08.

## Answer

Settled 2026-10-09.

- **Runner:** `scratch/nor_object_mi/simpler_first_dr_framed_deck_boards.py`
- **Arts:** `…/_nor_object_mi/simpler_first_dr_framed_deck_exemplar/`
- **Vault:** [[Run DR Framed Deck Exemplar]]

| Board | Result (computed) |
|-------|-------------------|
| A | ρ=0.937, n=139, hit |
| C | ladder ρ=0.804 n=1296; NOR_TX×nvl_obj ρ=0.719 n=144 |
| D | richness ρ=0.727 hit; shannon ρ=0.079 miss; hill2 ρ=−0.083 miss |
| E/F | exemplar prox shannon/richness/hill2 violins + session-step heatmaps written |
