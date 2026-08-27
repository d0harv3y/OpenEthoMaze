# Simpler first: tx on NOR phases × novel_obj

Question → folder map (canonical, next to artifacts):
`C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017\_nor_object_mi\README.md`

## Full-session grain (done — miss)

| Knob | Value |
|------|--------|
| Grain | animal × phase × `novel_obj`; all bout frames |
| Model | `paramscan_s1-1e8_s2-1e5_ss-50` raw |
| Result | Q1/Q2 miss at BL/TX/REC3hr/REC11hr |

## Near-object grain (locked 2026-08-13)

| Knob | Value |
|------|--------|
| Gate | **A**: `bout_mean_dist_any_m` < **0.10 m** (fixed; `spot`) |
| Grain | animal × phase × `novel_obj` × spot_bout_mean_any < 0.10 m (raw) |
| Keep rule | ≥ 50 gated frames / animal; else drop from preference & composition tests |
| Model | same pilot |
| Phases | `NOR_BL`, `NOR_TX`, `NOR_REC3hr`, `NOR_REC11hr` |

**Q1 redefined (among near bouts)**

- Primary: `pref_nvl_among_near` = frame-weighted P(`d_nvl` < `d_fam` | near)
- Companions: `delta_prox_among_near` = `d_fam − d_nvl` on gated bouts; `frac_near` = gated frames / session frames (engagement; uses all animals)

**Q2** — COUNT / Shannon / Bray–Curtis PERMANOVA (analogy-only) on gated syllable compositions.

**Hope:** BL quiet; TX or recovery may hit.

Runner: `uv run python scratch/nor_object_mi/simpler_first_near.py`

## Presence steps (simpler-first, paired) — locked 2026-08-13

Question: within animal, does engagement / syllable composition change
`no_obj → identical` (presence) and `identical → novel` (novelty)?

Not MI. Runner: `uv run python scratch/nor_object_mi/simpler_first_presence.py`

| Step | Plain question |
|------|----------------|
| S0 | `frac_near` / mean `dist_any` change? |
| S1 | richness / Shannon / paired Bray–Curtis change `no→id`? |
| S2 | same for `id→novel` |

Hope: S0/S1 light on presence; S2 quieter (matches MI ladder).

Grid: all 21 `paramscan_*` × BL/TX/REC3hr/REC11hr →
`presence_step_tests_long.csv` + `presence_step_deltas_per_animal.csv` +
`presence_step_agreement_by_model.csv`.

Data dictionary: `…/simpler_first_presence_steps/INFO_presence_steps.md`

Out: `…/_nor_object_mi/simpler_first_presence_steps/`

## Per-object 0.10 m proximity windows (object-prox DR) — locked 2026-08-18

Classic NOR discrimination ratio from presence occupancy: each object gets
its own `spot` proximity window of radius 0.10 m on `novel_obj`. Overlap audited.

```
DR = (T_nvl − T_fam) / (T_nvl + T_fam)
```

Runner: `uv run python scratch/nor_object_mi/simpler_first_object_prox.py`
Figures: `uv run python scratch/nor_object_mi/fig_simpler_first_object_prox.py`

Out: `…/_nor_object_mi/simpler_first_object_prox_0p10/`
Dictionary: `INFO_object_prox.md`

21-model result: **zero overlap** in all 84 model × phase cells (no dual-gated
bouts; min `d_fam+d_nvl` 0.29–0.32 m). Wilcoxon DR vs 0 hits 21/21 at BL / TX /
REC3hr; miss 0/21 at REC11hr. Kruskal on DR by tx: miss all sex × phase × model.
Occupancy Kruskal hits in three cells (not a DR claim). Inclusive = exclusive.

## Classic investigation DR vs object-prox DR — locked 2026-08-18

Same formula; classic T = IMPRESS nose/forelimb investigation
(`thresholded-signal-bouts/impress_exploration.csv`). Object-prox T = 21-model
median occupancy DR. Ambulation speed is a negative-control axis, not DR.

Runner: `uv run python scratch/nor_object_mi/simpler_first_classic_dr.py`
Figures: `uv run python scratch/nor_object_mi/fig_simpler_first_classic_dr.py`

Out: `…/_nor_object_mi/simpler_first_classic_dr/`
Dictionary: `INFO_classic_dr.md`

Result: Spearman ρ = 0.95–0.97 vs object-prox (hit all phases); |ρ| ≤ 0.16 vs
speed/immobile (miss). Wilcoxon vs 0 hits the same phases as object-prox.
Not a syllable composition.

## Movement vs syllable clocks — locked 2026-08-19

Movement bouts (IMPRESS `fore` hysteresis) vs syllable bouts (locked kpMS
duration/count). Different clocks; NOR ladders have no bout speed.

Runner: `uv run python scratch/nor_object_mi/simpler_first_ambulation_clocks.py`
Figures: `uv run python scratch/nor_object_mi/fig_simpler_first_ambulation_clocks.py`
Out: `…/_nor_object_mi/simpler_first_ambulation_clocks/`

~25 movement bouts vs ~230 syllable bouts. n-clocks Spearman ρ = 0.26–0.67.
Distance litmus ρ ≥ 0.99. Speed vs classic DR miss.

## DA on presence/novelty steps — locked 2026-08-17

Which syllables change relative use on the same paired condition steps?
Not Shannon. Runner: `uv run python scratch/nor_object_mi/simpler_first_da.py`

| Knob | Value |
|------|--------|
| Grain | animal × phase × condition (full session; same bouts as presence) |
| Test | Wilcoxon on Δp_k; BH FDR within model × phase × step |
| Companion | L1-share of paired BC (descriptive) |
| Consistency | Jaccard / Spearman of median Δp **within model** across phases |

Out: `…/_nor_object_mi/simpler_first_da/`

## Between-phase, same condition — locked 2026-08-17

Same animal, **condition held**, pair phases (BL→TX, TX→REC3hr, REC3hr→REC11hr,
BL→REC11hr). Not the old phase grid (tx Kruskal inside each phase).

Runner: `uv run python scratch/nor_object_mi/simpler_first_phase_paired.py`
Figures: `uv run python scratch/nor_object_mi/fig_simpler_first_phase_paired.py`

Out: `…/_nor_object_mi/simpler_first_phase_paired/`
Dictionary: `INFO_phase_paired.md`
