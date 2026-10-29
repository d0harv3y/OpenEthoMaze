# Exemplar pause syllable assets (syll 5)

Type: research
Status: resolved
Blocked by:

## Question

For exemplar model `paramscan_s1-1e7_s2-3e4_ss-100`, `raw_syllable_id` 5 maps to cross-model `cluster_id` 13. What **figures / tables** already exist for that syllable (Δp, frame share, trajectory GIF, info_dr_pause joins), and what is missing for a still↔pause collinearity panel?

Fact already known: `cluster13_syllable_map.csv` → raw_id **5**, n_bouts≈22419. Do not brand the slide as cluster13; use “pause syllable (exemplar)” / syll5.

## Answer

**Map confirmed:** `slides_pack/cluster13/cluster13_syllable_map.csv` and `simpler_first_da/cluster13_syllable_map.csv` both map exemplar `paramscan_s1-1e7_s2-3e4_ss-100` → `raw_syllable_id` **5**, `cluster_id` 13, `n_bouts` 22419. `duration_band_vs_da.csv` same row (occupancy≈0.166, median bout 31 frames, `da_hit_fdr05` True). Slide brand: **pause syllable / syll5**, not cluster13.

### Inventory (exists)

| Kind | Path (under `D:\sack\datas\impress\moseq_251017\` unless noted) | Notes |
|------|------------------------------------------------------------------|-------|
| Trajectory GIF | `paramscan_s1-1e7_s2-3e4_ss-100/trajectories/Syllable5.gif` (+ `all_trajectories.gif`) | Exemplar-native kinematic preview |
| Grid movie | `_nor_object_mi/simpler_first_da/grid_movies/grid_condition_argmax_s1-1e7_s2-3e4_ss-100_syll5_cluster13.mp4` | Filename has cluster13; slide copy should say syll5 |
| Frame share (exemplar, animal×session×trial) | `D:\sack\crosscorr\out_spearman_moseq_physio\moseq_251017\paramscan_s1-1e7_s2-3e4_ss-100\tables\syllable_frame_share_long.csv` | Filter `syllable==5`; 1296 rows; also physio Spearman heatmaps in sibling `heatmaps/` |
| Δp / level p (exemplar syll5) | `_nor_object_mi/simpler_first_da/da_syllable_deltas_per_animal.csv` | Filter `model==…ss-100` & `raw_syllable_id==5` → 1296 rows; steps `no_obj→id_obj`, `id_obj→nvl_obj`, `no_obj→nvl_obj`; cols `p_left`, `p_right`, `delta_p` |
| Δp (exemplar, cluster-mapped) | `…/simpler_first_da/cluster13_model_animal_delta_p.csv` | Same exemplar filter; one syllable per model → equals syll5 Δp |
| Consensus pause Δp / frame share | `cluster13_animal_median_delta_p.csv`; `slides_pack/cluster13/cluster13_animal_frame_share.csv` + Kruskal / step-Δ CSVs | **Median across 21 models** — not exemplar-only |
| Condition Kruskal / DA figs | `fig_cluster13_*`, `model_syllable_condition_kruskal/…_ss-100.svg`, volcano ladders for exemplar | Alphabet / protocol-step story; fit-local cluster id in filenames |
| Spatial (cluster filter) | `syllable_spatial_heatmaps_cluster13/` (+ `_condition_overlay/`) | Descriptive dwell; not animal-scalar join |
| `frac_still` pack (Layer A clock) | `slides_pack/frac_still/` — animal CSV, Kruskal, trial-/session-step Δ, `fig_frac_still_*.svg` | Parallel to pause pack; **not joined** to syll5 |
| Stillness companion (I on still alone) | `simpler_first_stillness_companion_audit/` — `Stillness-Companion-A` Kruskal at `NOR_REC3hr×no_obj` | Vault [[F Stillness-Companion-A]]; **not** still↔pause association |
| info_dr_pause joins | `simpler_first_info_dr_pause/` (+ forks `__p_novel`, `__presence_*`, `__delta_p_presence`, `_mi_mm_nvl`) | Joins **object-prox DR × consensus pause Δp** (21-model median); scatter/heatmaps exist. **Not** still×pause; **not** exemplar-only syll5 |
| Locomotor ∩ syll | `simpler_first_syll_ambulation_overlap/` | Locked model is `…s1-1e8_s2-1e5_ss-50`, not exemplar; MI of syllable id × move/still |
| Vault prose | `docs/vaults/moseq-fishing` — Honest Report §1, [[Run Slides Pack]], [[Run Info Dr Pause]], [[Run Syll Ambulation Overlap]] | Claims still↔pause collinearity narratively; cites parallel packs, not a join board |

**Spot-check (joinable raw inputs, no shipped fig):** `frac_still_animal.csv` ⋈ exemplar `syllable_frame_share_long` (`syllable==5`) → 1296/1296 rows; Spearman ρ(`frac_still`, share) ≈ **0.80**. At `nvl_obj`, ρ(`frac_still`, `p_right`) ≈ 0.77; ρ vs novelty `delta_p` ≈ 0.37.

### Gaps (still↔pause collinearity panel)

Board C in `05-join-board-contracts.md` needs a **declared join** — not parallel violins.

Missing:

1. **Joined table** — animal × (declared session×trial) with `frac_still` (or `time_immobile_s`) and exemplar syll5 frame-share and/or Δp; INFO + Spearman cousins.
2. **Scatter (+ optional heatmap)** — still vs syll5 share/Δp; brand “pause syllable (exemplar) / syll5”.
3. **INFO / tests long** — analogous to `info_dr_pause_*` but Y = still clock, X = exemplar syll5 (or vice versa); grain eligibility locked in issue 05.
4. **Exemplar-only framing** — existing pause decks and `info_dr_pause` are mostly **consensus cluster13**; must slice exemplar model (or rebuild from `da_syllable_deltas` / crosscorr share) for the slide brand.
5. **Do not reuse as the panel:** `Stillness-Companion-A` (condition Kruskal on still alone); `info_dr_pause` (DR×pause, not still×pause); cluster13 consensus violins alone; ambulation-overlap locked to a different model.

**Reuse without new compute (inputs only):** `slides_pack/frac_still/frac_still_animal.csv` + crosscorr exemplar `syllable_frame_share_long.csv` (share) and/or `da_syllable_deltas_per_animal.csv` (Δp / `p_right`). GIF + grid mp4 ready for the kinematic inset.
