---
title: Run Alphabet Equate Soft Shape
type: run
assay: nor-impress
status: ladder
claim_kind: alphabet-bound
verdict: na
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - alphabet-bound
---
# Run Alphabet Equate Soft Shape

**Status:** computed (2026-10-07) — cheap (0)+(1) poke on pooled + per-animal. #ladder #alphabet-bound  
**Parent:** [[H Alphabet Equating]]

## Intent

(0) Soft leave-animal-out NN + accent residualize (nose–tail median within animal) instead of HDBSCAN-as-equate.  
(1) Shape-of-bout scalars (peak / time-to-peak / accel–decel asym / still duty / nose–tail Δ / turn p90 / curvature) alongside classic 9 mean/IQR columns.

Same protocol on **pooled** `moseq_251017` and **per-animal** `nor_per_animal_paramscan`. Grain: `(animal_id, model, raw_syllable_id)`. D only.

## Bearing (D)

Lower `mean_cross_animal_1nn_dist` = easier soft equate. Lower `frac_5nn_same_animal` = less accent clumping.

| Layout              | Feature set     | cross-animal 1NN | 5NN same-animal | HDBSCAN k |
| ------------------- | --------------- | ---------------- | --------------- | --------- |
| per-animal (n≈7.9k) | baseline9       | 0.554            | 0.316           | 2         |
| per-animal          | + accent resid  | 0.555            | **0.296**       | 6         |
| per-animal          | + shape         | 0.989            | 0.357           | 3         |
| per-animal          | + shape + resid | 1.005            | 0.351           | 3         |
| pooled (n≈105k)     | baseline9       | 0.359            | 0.149           | 3         |
| pooled              | + accent resid  | **0.356**        | **0.130**       | 3         |
| pooled              | + shape         | 0.651            | 0.150           | 5         |
| pooled              | + shape + resid | 0.652            | 0.139           | 5         |

**Read:** Accent residualize helps a little (same-animal neighborhood purity ↓). Shape-of-bout **worsens** soft NN distance on both layouts (higher-dim mush / animal-idiosyncratic timing). Per-animal 5NN animal-purity ≈2× pooled — local alphabets clump by animal even in kinematics. HDBSCAN still collapses to ~2–6 islands (foil).

## Links

- Hypothesis: [[H Alphabet Equating]]
- Cousins: [[Run Per Animal Prototype Ordination]] · [[Run Syllable Signatures]]

## Artifacts

| Campaign | Root |
|----------|------|
| Pooled | `sack/datas/impress/moseq_251017/_nor_object_mi/alphabet_equate_soft_shape/` |
| Per-animal | `sack/datas/impress/nor_per_animal_paramscan/_nor_object_mi/alphabet_equate_soft_shape/` |

| File | Role |
|------|------|
| `prototypes_animal_model_syllable.csv` | D — prototypes + shape cols |
| `run_summary.json` | Soft NN + HDBSCAN foil per feature set |
| `figures/fig_alphabet_equate_soft_shape_pca.*` | PCA panels by feature set |
| `figures/fig_alphabet_equate_soft_shape_pca3d.html` | Plotly 3D animal-resolved + strata checkboxes |
| `figures/fig_alphabet_equate_soft_shape_pca3d_avganimal.html` | Plotly 3D after averaging animals → model×syllable (signatures grain) |
| `prototypes_model_syllable_avganimal.csv` | D — animal-averaged prototypes |
| `INFO_alphabet_equate_soft_shape.md` | Data dictionary |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/alphabet_equate_soft_shape.py`  
**Plotly 3D:** `…/alphabet_equate_soft_shape_plotly3d.py`

```powershell
uv run python scratch/nor_object_mi/alphabet_equate_soft_shape.py --layout pooled --clean
uv run python scratch/nor_object_mi/alphabet_equate_soft_shape.py --layout per_animal --clean
uv run python scratch/nor_object_mi/alphabet_equate_soft_shape_plotly3d.py --layout per_animal
uv run python scratch/nor_object_mi/alphabet_equate_soft_shape_plotly3d.py --layout pooled
```

## Related

- [[H Alphabet Equating]] · [[Run Per Animal Prototype Ordination]] · [[Claim Kind]]
