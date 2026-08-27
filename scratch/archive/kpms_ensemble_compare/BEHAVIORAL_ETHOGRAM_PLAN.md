# Behavioral ethogram — grill synthesis (2026-06-22)

Design locked via grill-with-docs. Domain language: [CONTEXT.md](./CONTEXT.md). ADRs: [docs/adr/](./docs/adr/).

## Phased roadmap

| Phase | Goal | Key outputs |
|-------|------|-------------|
| **I** | Stable cross-seed behavior tokens | Anatomical `shared/` clustering (`--phase all`); scalar sidecars; blob/fused contrast join; bout speed IQR → `ambiguous` |
| **II** | Locomotion tiers | `locomotion_tiers.yaml` (default); histogram calibration → data-driven thresholds; tier-colored block ethograms |
| **IIIa** | Still-behavior names | `still_behavior_labels.csv`; exemplar bout review; freeze vs groom via anatomical–blob contrast |
| **IIIb** | Full ontology | Grid-movie pass on all tokens (after IIIa stable) |

## Locked decisions (Q1–Q9)

1. **I → II → III** (Roman numerals)
2. Token on **syllable prototype**; bout stats = QC gate
3. **Scalars now**, pose-shape Phase III; `is_moving` provisional
4. **Anatomical primary**; blob contrast; fused validates
5. Store contrast Phase I; **anatomical-only tiers** Phase II; split still Phase III
6. **YAML tier default** → histogram-calibrated data-driven
7. **`phase=all`** token tables; RUN/ITI split at export only
8. **`ambiguous`** = prototype bout speed IQR (not cluster-level)
9. **IIIa still pass now**; IIIb full naming later

## Implementation order (scratch → library)

### Step 1 — Phase I anatomical (exists, extend)

```powershell
uv run python scratch/kpms_ensemble_compare/syllable_speed_cluster.py `
  --scope per-stream --phase all --models anatomical `
  --kpms-root ... --legacy-db ... --manifest-path ... --out-dir ...
```

**Extend `syllable_speed_cluster.py`:**
- Add scalars to labels: `frac_still`, `mean_abs_dheading`, `bout_speed_iqr`
- Flag `ambiguous` per prototype (ADR 0007)

**New: cross-stream join script**
- Match `(seed, raw_id)` across anatomical / blob / fused prototype tables
- Emit `contrast_sidecar.csv`: `delta_speed_ab`, fused validation flags

Repeat clustering for blob + fused (validation only).

### Step 2 — Phase II calibration + tiers

**New: `calibrate_locomotion_tiers.py`**
- Scatter/histogram of token scalars from anatomical `shared/hdbscan_labels.csv`
- Provisional YAML tier assignment + `ambiguous` exclusion
- Output: `locomotion_tiers.yaml`, `token_tiers.csv`

**Extend `block_ethogram_exports.py`:**
- `--tier-color` flag: syllable id → token → tier color (anatomical lookup)

### Step 3 — Phase IIIa review kit

**New: `pick_still_exemplars.py`**
- Filter `token_tiers.csv` where `tier == still` and not `ambiguous`
- Rank by `delta_speed_ab`; pick 3–5 bouts per token
- Emit grid movies or trial list for `still_behavior_labels.csv` template

## Hypothesis table (Phase IIIa)

See full candidate ontology: [ONTOLOGY.md](./ONTOLOGY.md).

| Pattern | Anatomical speed | Blob speed | Fused agrees? | IIIa label |
|---------|------------------|------------|---------------|------------|
| Freeze candidate | very low | very low | yes | freeze |
| Groom candidate | low–moderate local | very low | yes | groom |
| Other still (defer) | low | low | — | other_still → IIIb (sniff, stretch, …) |
| Ambiguous | — | — | no | unsure |

## What not to do

- Rename raw syllable ids and call it an ethogram
- Use `speed_index` as locomotion tier
- Split freeze/groom in Phase II YAML
- Trust `is_moving` over `mean_speed_mps` when they disagree

## Open follow-ups

- Retune ambulation debounce on this cohort (optional; does not block Phase I if clustering stays curve-based)
- Pose-shape features for rearing / probe (Phase IIIb)
- Promote scratch scripts to `maze/cli` after test2 validation

---

## Where everything is written (storage)

See [ADR 0009](docs/adr/0009-storage-layout.md). Short version:

### In git (design only)

| Path | Contents |
|------|----------|
| `scratch/kpms_ensemble_compare/CONTEXT.md` | Ubiquitous language |
| `scratch/kpms_ensemble_compare/docs/adr/` | Locked decisions |
| `scratch/kpms_ensemble_compare/BEHAVIORAL_ETHOGRAM_PLAN.md` | This plan |

### On cohort disk (`test2/` example)

| Path | Write? | Contents |
|------|--------|----------|
| `kpms_tracking.h5` | **No** (read pose) | SLEAP/anatomical/blob streams for kpMS |
| `../test/vast_results_legacy.h5` | **No** (read ambulation) | `is_moving`, spot xy, exploration |
| `{stream}/seed_{NNN}/results_apply.h5` | **kpMS apply only** | Raw per-frame `syllable` vectors |
| **`behavior_ethogram/`** | **Yes — cohort tables** | Phase I–III CSV/YAML/JSON (tokens, tiers, contrast, review) |
| `block_ethogram_exports/` | **Yes — viz** | PNGs, `DATA_DICTIONARY.md`, legends |

### Data flow

```
results_apply.h5 (read syllable_id per frame)
        +
vast_results_legacy.h5 (read speed, is_moving)
        +
kpms_tracking.h5 (read pose if needed later)
        ↓
behavior_ethogram/phase_i/   ← clustering + contrast (write)
        ↓
behavior_ethogram/phase_ii/  ← tiers YAML + token_tiers.csv (write)
        ↓
block_ethogram_exports/      ← PNGs colored by tier/token (write)
        ↓
behavior_ethogram/phase_iii/ ← human labels (write)
        ↓
(later) trial H5 ethogram/   ← optional per-frame cache of derived token/tier
(later) bout CSV export      ← derived rows for stats
```

**Rule of thumb:** H5 files hold **timelines** (pose, ambulation, raw syllables). New **lookup and review** artifacts live under `behavior_ethogram/`. Do not stuff cohort-wide token tables into per-model `results_apply.h5` or legacy ambulation H5.
