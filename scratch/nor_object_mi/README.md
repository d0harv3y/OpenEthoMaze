# NOR object-distance MI (scratch pilot)

**Question → run-folder map (canonical):**
`C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017\_nor_object_mi\README.md`

That catalog is the narrative order (reproduce original → protocol check →
snapshots → controlled evolution, `noSD` Wilcoxon within sex → then tx).
Dictionaries live next to artifacts (`INFO_*.md` in each run folder), not here.

Bout-level mutual information (MI) between keypoint-MoSeq (kpMS) syllables and
distance-to-object bins on Novel Object Recognition (NOR) data.

**Not library code** — lives under gitignored `scratch/`. Promote to `maze/kpms/`
only after the pilot claim clears.

## Defaults (locked 2026-08-10)

| Knob | Value |
|------|--------|
| Keypoint | **`spot`** = mean(nose, neck, spine) in px, then / `pixels_per_meter` → meters |
| Pilot phase | **`NOR_TX` only** (`phase_layer`) |
| Pilot model | `paramscan_s1-1e8_s2-1e5_ss-50` |
| Cohort filter | Drop non-animal / blank `tx`/`sex`; log **N and IDs** in `cohort_filter.json` |
| Primary claim | Treatment × novelty via `Δ = excess_I(dist_nvl) − excess_I(dist_fam)` on `novel_obj` |
| Distance bins | **5 shared** quantiles on pooled bout-mean spot→object distance from **`novel_obj` + `identical_obj`**; same edges for fam & nvl. **`no_obj` excluded** for now |
| Code home | `scratch/nor_object_mi/` |

Note: classic NOR *investigation* metrics use forelimb keypoints
(`nose, neck, foreL, foreR`). This pilot uses **`spot`** (ambulation synthetic),
per explicit choice.

**`no_obj` pseudo-targets (presence question):** objects occupy two arena loci;
`which` locus holds the novel object varies. For `no_obj`, loci = 2-means of that
animal×phase centers from `identical_obj` + `novel_obj`; `dist_any` = nearest locus.

## Presence question (identical vs no_obj)

```powershell
uv run python scratch/nor_object_mi/run_presence_pilot.py `
  --nor-h5 "C:\Users\admin\Documents\work\sack\datas\impress\my_NOR_results.h5" `
  --kpms-results "C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017\paramscan_s1-1e8_s2-1e5_ss-50\results.h5" `
  --out-dir "C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017\_nor_object_mi\paramscan_s1-1e8_s2-1e5_ss-50\presence" `
  --phase-layer NOR_TX `
  --n-bins 5 `
  --n-perm 100 `
  --seed 42
```

Claim: paired `Δ_presence = excess_I(dist_any|identical) − excess_I(dist_any|no_obj)`
(shared `dist_any` quantile bins; circular null). Also tx × sex on that Δ.

**Figure (pub-style):** regenerate with

```powershell
uv run python scratch/nor_object_mi/fig_presence_excess_mi.py
```

Outputs:
`.../presence/fig_presence_excess_mi.pdf` and `.png`

## Data roots

```
NOR geometry:  .../sack/datas/impress/my_NOR_results.h5
kpMS ensemble: .../sack/datas/impress/moseq_251017/paramscan_*/
videos:        .../sack/datas/impress/standard format/
```

## Pilot run (PowerShell)

From OpenEthoMaze repo root:

```powershell
uv run python scratch/nor_object_mi/run_pilot.py `
  --nor-h5 "C:\Users\admin\Documents\work\sack\datas\impress\my_NOR_results.h5" `
  --kpms-results "C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017\paramscan_s1-1e8_s2-1e5_ss-50\results.h5" `
  --out-dir "C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017\_nor_object_mi\paramscan_s1-1e8_s2-1e5_ss-50" `
  --phase-layer NOR_TX `
  --n-bins 5 `
  --n-perm 200 `
  --seed 42
```

Artifacts under `--out-dir`:

- `cohort_filter.json` — kept / dropped IDs + N
- `session_join.csv` — kpMS key ↔ NOR session (pilot phase slice)
- `object_bout_features.csv` — syllable bouts + bout-mean `dist_fam_m` / `dist_nvl_m`
- `bin_edges.json` — shared `dist` quantiles (`n_bins=5`; any-object bout means; mirrored to `dist_fam`/`dist_nvl`)
- `mi_per_animal.csv` — per animal × stim_var (`dist_fam` / `dist_nvl`) occupancy MI
- `mi_delta_per_animal.csv` — novelty contrast `Δ`
- `group_delta_tests.csv` — Kruskal / Mann–Whitney on `Δ` by `tx` and `sex`, **pooled and sex-stratified** (`sex_stratum` = `all` | `F` | `M`; also within-tx sex contrasts as `tx=…`)
- `run_summary.json`

## Presence ensemble grid (done)

```powershell
uv run python scratch/nor_object_mi/run_presence_grid.py --workers 3 --n-perm 100 --seed 42
uv run python scratch/nor_object_mi/fig_presence_grid_summary.py
```

Frozen `dist_any` edges from ref pilot TX
(`…/paramscan_s1-1e8_s2-1e5_ss-50/presence/bin_edges_dist_any.json`).
Artifacts: `_nor_object_mi/presence_grid_summary.csv`,
`fig_presence_grid_summary.pdf/.png`, plus per-model `presence/` /
`presence_NOR_BL/`.

**2026-08-10 result (exploratory `n_perm=100`):** all **21/21** models,
both **NOR_BL** and **NOR_TX**, have median `Δ_presence > 0` and Wilcoxon
`p < 0.05` (actually all `p < 0.001`). Tx Kruskal on Δ: **0/21** BL,
**1/21** TX (`s1-1e7_s2-1e5_ss-50`, p≈0.042 — expected-rate noise at α=0.05).

## Independent loci (presence secondary)

Same present/absent contrast, but stimulus = distance to spatially labeled
locus A or B (animal×phase 2-means, lower-x = A; identical centers matched to
A/B). Nearest (`dist_any`) recomputed in the same run for comparison.

```powershell
uv run python scratch/nor_object_mi/run_presence_loci_pilot.py `
  --nor-h5 "C:\Users\admin\Documents\work\sack\datas\impress\my_NOR_results.h5" `
  --kpms-results "C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017\paramscan_s1-1e8_s2-1e5_ss-50\results.h5" `
  --out-dir "…\_nor_object_mi\paramscan_s1-1e8_s2-1e5_ss-50\presence_loci" `
  --phase-layer NOR_TX --n-perm 100 --seed 42 `
  --bin-edges-json "…\presence\bin_edges_dist_any.json"
uv run python scratch/nor_object_mi/fig_presence_loci_independent.py
```

Ref pilot (frozen edges): presence boost survives per locus, but median Δ is
smaller than nearest (nearest packs both objects into one channel).

## Novelty × fixed historical loci

Distance targets for spatial channels = **fixed** animal×phase 2-means (not
session centers). Tag ``nvl_nearest_hist_locus`` = which hist locus is nearer
the session novel-object center. Contrasts:

- Δ_nov = excess_nvl − excess_fam (session role centers)
- Δ_spa = excess_hist_B − excess_hist_A
- Δ_side = excess(nvl-side hist) − excess(other hist)

```powershell
uv run python scratch/nor_object_mi/run_novelty_loci_pilot.py `
  --out-dir "…\novelty_hist_loci" --phase-layer NOR_TX --n-perm 100 `
  --bin-edges-json "…\bin_edges.json"
uv run python scratch/nor_object_mi/fig_novelty_hist_loci.py
```

Ref TX: all three Δ ~0 (Wilcoxon NS). Nvl sits at hist **B** in 143/144 animals
(BL: hist **A** in 141/144) — strong phase-locked placement, so Δ_side ≈ ±Δ_spa
for most animals. Role Δ remains null; tagging works.

## Simpler first (tx before MI)

One-page plan: `simpler_first_plan.md`. Locked cell = `NOR_TX` × `novel_obj` window ×
pilot model, raw bouts. Q1 proximity (`Δ_prox`); Q2 syllable composition; Q3 INFO/MI only after a hit.

**Presence steps** (paired conditions inside a phase):

```powershell
uv run python scratch/nor_object_mi/simpler_first_presence.py
```

**DA** (which syllables move on those steps; BH within model × phase × step):

```powershell
uv run python scratch/nor_object_mi/simpler_first_da.py
```

**Between-phase, same condition** (paired phases, condition held):

```powershell
uv run python scratch/nor_object_mi/simpler_first_phase_paired.py
```

Litmus: `uv run pytest scratch/nor_object_mi/test_simpler_first_presence.py scratch/nor_object_mi/test_simpler_first_da.py scratch/nor_object_mi/test_simpler_first_phase_paired.py scratch/nor_object_mi/test_simpler_first_object_prox.py scratch/nor_object_mi/test_simpler_first_classic_dr.py scratch/nor_object_mi/test_simpler_first_ambulation_clocks.py -q`

## Condition ladder (fam-side / nvl-side)

Panel A: `no_obj` → `identical` → `fam_obj` on the **fam-side** hist locus  
(tag from novel session). Panel B: same ladder on the **nvl-side**.

```powershell
uv run python scratch/nor_object_mi/run_condition_ladder.py `
  --out-dir "…\condition_ladder" --phase-layer NOR_TX --n-perm 100 `
  --bin-edges-json "…\bin_edges.json"
uv run python scratch/nor_object_mi/fig_condition_ladder.py
```

Ref TX: presence step (no→id) rises on both sides; id→role-object step is NS
(no extra novelty/familiar boost beyond objects being present).

## Full-grid plan (novelty question; presence done)

1. Freeze `bin_edges.json` from the pilot model (shared any-object edges from novel+identical; exclude no_obj).
2. Fan out `run_pilot.py` over all 21 `paramscan_*` dirs (same `--phase-layer`, seed, edges).
3. Aggregate `Δ` medians / tx p-values into a model × contrast table.
4. **Survive model choice:** sign(`median_Δ` by tx contrast) and null-clear fraction stable across grid.
5. If that fails, rank models by novel_obj `excess_I(dist_nvl)` (object-conditioned winner) as fallback.
6. Optionally expand phase to `NOR_BL` / REC after TX clears.
7. **Presence question (implemented + ensembled):** `run_presence_pilot.py` /
   `run_presence_grid.py` — `excess_I(dist_any)` on `identical_obj` vs `no_obj`
   pseudo-loci. Keep **BL and TX separate**; do **not** average phases when
   hunting tx effects that appear only after treatment. Optional per-animal
   change: `Δ_TX − Δ_BL`.
8. **Discrimination ratio on per-object 0.10 m proximity windows (implemented, 21 models):**
   `simpler_first_object_prox.py` — `DR = (T_nvl − T_fam) / (T_nvl + T_fam)`
   on `novel_obj` with independent fam/nvl gates. Overlap audited (zero in all
   21 × 4 cells). Figures: `fig_simpler_first_object_prox.py` (occupancy is
   two 16:9 1×4 packs, fam vs nvl). Classic
   investigation DR comparison: `simpler_first_classic_dr.py` (same formula;
   not a syllable composition). Not the unused MI form `DI_MI` below.
9. **Optional companion metric (not implemented):** discrimination-style
   `DI_MI = (excess_nvl − excess_fam) / (excess_nvl + excess_fam)`, gated when
   `excess_nvl + excess_fam > ε` (excess can be ≤0 → unstable DI). Keep primary
   stats on additive `Δ`; run DI tests only on the gated subset. Alt: `Δ / H(syll)`.

## Confounds (report, do not bury)

- Proximity ↔ slowing ↔ investigate-like syllables.
- Raw MI favors high-entropy (short-bout) models — use **excess** / compare `Δ`, not raw `I`.
- `no_obj` / `identical_obj` are controls (built into bout table when present; MI primary = `novel_obj`).
