# Handoff — kpMS ensemble test2, block ethograms, syllable speed clustering

**Date:** 2026-06-22  
**Repo:** `c:\Users\admin\code\OpenEthoMaze`  
**Prior chat:** [agent transcript](eaf93259-b3b4-4b5f-b354-6fdf20defb51) (full JSONL in Cursor agent-transcripts)  
**User scratch commands:** `my_todo.txt` lines 41–78

---

## Mission (current arc)

Lab analysis on **test2** kpMS ensemble (15 models: 3 streams × 5 seeds). Deliver stratified **block ethogram** exports (Emma|Hayden dwell-like cohort), **speed-ranked / kinematic clustering** of syllables for visual comparison, and optional integration with ensemble compare (`scratch/kpms_ensemble_compare/`). Scratch-first; promote to `maze/` later if validated.

---

## Data locations

| Resource | Path |
|----------|------|
| kpMS root (15 fits/applies) | `C:\Users\admin\Documents\work\sack\test2` |
| Legacy ambulation H5 | `C:\Users\admin\Documents\work\sack\test\vast_results_legacy.h5` |
| Manifest | `C:\Users\admin\Documents\work\sack\test2\trial_manifest_kpms_tracking.csv` |
| Ethogram + cluster outputs | `C:\Users\admin\Documents\work\sack\test2\block_ethogram_exports\` |
| Ensemble compare outputs | `scratch/kpms_ensemble_compare/output/test2/` |

test2 has **no** legacy H5; movement joins always use **test** legacy DB.

---

## Shipped scratch code (not necessarily committed)

### Block ethograms v2 — `scratch/kpms_ensemble_compare/block_ethogram_exports.py`

- **3 rows:** stacked syllable bars (height = n(t)) | mean occupancy line ± SEM | entropy line ± bootstrap SEM (100 draws).
- **Time:** 0.333 s bins; mode syllable per trial per bin.
- **Colors:** matplotlib `jet(syllable_id / max_id)`; stack order = global occupancy ascending (rare bottom).
- **Bars:** full bin width, edge-aligned (fixed vertical stripe artifact from `width=0.95`).
- **Global artifacts** at export root: `DATA_DICTIONARY.md`, `legend.png`.
- **Per-model** `{out}/{stream}/seed_{NNN}/legend.png`.
- **CLI:** `--speed-reindex` reads `speed_rank_table.csv` or `speed_rank_table_{run|iti}.csv` from model dir for jet color + stack order.
- Cohort filters, layout, filename convention: see `DATA_DICTIONARY.md` at export root.

### Syllable speed + HDBSCAN — `scratch/kpms_ensemble_compare/syllable_speed_cluster.py`

- **Per-model** (default): bout curves → z-score → HDBSCAN → motif grid + CSVs.
- **Features:** median bout curve on τ∈[0,1] of `[speed, cos θ, sin θ]`; adaptive `T_s = clip(round(1.5×median_bout_frames), 8, 30)`; pad to `T_max` with **per-syllable channel mean** (documented experiment; may leak bout length).
- **HDBSCAN:** `min_cluster_size = max(3, ⌈2%×n⌉)`, `min_samples=2`, overridable; noise cluster `-1` shown unless `--drop-noise`.
- **CLI:** `--phase all|run|iti`, `--min-bout-frames 4`, `--min-occupancy 0.1` (0=off), `--motif-style centroid` (trajectory flag reserved).
- **Outputs per model:** `speed_rank_table.csv`, `hdbscan_labels.csv`, `cluster_inequality.csv`, `speed_motif_grid.png`, `legend.png`.

### Movement layer — `scratch/kpms_ensemble_compare/movement_layer.py`

- Joins legacy `spot`/centroid ambulation to kpMS rows via `source_frames`.

### Dependency

- `hdbscan>=0.8.33` added to `[project.optional-dependencies] kpms` in `pyproject.toml` (`uv lock` already run in session).

---

## Critical bugfix (must re-run affected exports)

**Speed units:** `_speed_from_xy` previously computed **px/s** while labeling `speed_mps`. Fixed: `dist_m = dist_px / (px_per_cm × 100)`, `px_per_cm` from per-trial legacy H5 attrs.

**Impact:** All `speed_rank_table.csv`, clustering, and inequality metrics generated **before** this fix used wrong magnitudes (values ~5–96 were px/s, not m/s). **Re-run** `syllable_speed_cluster.py` then ethograms with `--speed-reindex` after fix.

---

## Grill-me spec (locked, not all implemented)

Design session covered speed re-index, HDBSCAN vs k-means, bout-curve features (not mean heading vector), padding choice A with disclaimer, slice B implementation order. Full Q&A in transcript above.

**Not implemented yet:**

| Item | Status |
|------|--------|
| `--scope per-stream` (pool seeds, shared HDBSCAN per stream) | In `my_todo.txt` commands; **not in code** — user asked what would change; design outlined in chat |
| `--motif-style trajectory` (kpMS `get_typical_trajectories`) | Flag reserved |
| Cross-stream / 15-model clustering | Design only; streams treated incomparable in `scratch/kpms_ensemble_compare/README.md` |
| Full 15-model × run/iti ethogram sweep | User runs locally |
| Promote scratch → `maze/cli` | Deferred |

**Cross-seed per stream (next logical feature):** pool rows `(seed, raw_id)`, one HDBSCAN per stream, emit `anatomical/shared/hdbscan_labels.csv` + per-seed map for ethogram reindex. See transcript for artifact layout.

---

## Other ensemble context (earlier in same arc)

- `run_compare.py` on test2: boundary F1, movement layer; `fused/seed_005` incomplete on old runs.
- Apply OOM fix: `--apply-workers 1`, JAX cache clear in `maze/kpms/apply.py`.
- CPU ensemble sweep: `maze-kpms-cpu-ensemble-sweep`.
- Reference dwell pattern: `maze/pipeline/viz/block_dwell_average.py`, `maze-average-block-dwell-plots`.

---

## Commands (PowerShell)

```powershell
cd C:\Users\admin\code\OpenEthoMaze
uv sync --extra kpms

# Cluster one model (after speed fix)
uv run python scratch/kpms_ensemble_compare/syllable_speed_cluster.py `
  --kpms-root "C:\Users\admin\Documents\work\sack\test2" `
  --legacy-db "C:\Users\admin\Documents\work\sack\test\vast_results_legacy.h5" `
  --manifest-path "C:\Users\admin\Documents\work\sack\test2\trial_manifest_kpms_tracking.csv" `
  --out-dir "C:\Users\admin\Documents\work\sack\test2\block_ethogram_exports" `
  --models anatomical/seed_042 --phase run

# Ethograms + speed-ranked colors
uv run python scratch/kpms_ensemble_compare/block_ethogram_exports.py `
  --kpms-root "C:\Users\admin\Documents\work\sack\test2" `
  --legacy-db "C:\Users\admin\Documents\work\sack\test\vast_results_legacy.h5" `
  --manifest-path "C:\Users\admin\Documents\work\sack\test2\trial_manifest_kpms_tracking.csv" `
  --out-dir "C:\Users\admin\Documents\work\sack\test2\block_ethogram_exports" `
  --models anatomical/seed_005 --speed-reindex --phases run `
  --no-full-session --no-all-sessions
```

Smoke timings: ~6–8 min per model for clustering; ~6+ min for ethogram block subset.

---

## Active / in-flight (at handoff)

User terminal was running **block ethogram export** for `anatomical/seed_005` with `--speed-reindex`, `--phases run`, full session flags off. May be using **pre-fix** `speed_rank_table.csv` unless cluster was re-run after movement_layer fix.

---

## Suggested skills (next agent)

| Skill | When |
|-------|------|
| **grill-me** (`c:\Users\admin\.agents\skills\grill-me\SKILL.md`) | Lock `--scope per-stream` API, cross-stream scope, or trajectory motifs |
| **investigation** (`c:\Users\admin\.agents\skills\investigation\SKILL.md`) | If padding/leakage or cluster semantics need empirical validation |
| **verify-this** (cursor-team-kit) | Confirm speed m/s after fix on one trial vs `amb_run.mean_speed_mps` in legacy H5 |
| **review** (`c:\Users\admin\.agents\skills\review\SKILL.md`) | Before promoting scratch scripts to `maze/cli` |
| **teach** (`c:\Users\admin\.agents\skills\teach\SKILL.md`) | User wanted motion-clustering pedagogy; optional MISSION in teaching workspace |

---

## Do not edit (unless user asks)

- `scripts/archive/**`, `maze/pipeline/paths_local.py`, Phase E ethogram GUI (`docs/ethogram_scope.md`).
- No git commits unless user requests.

---

## Open questions for next session

1. Implement **`--scope per-stream`** as sketched in `my_todo.txt`?
2. Re-run **all** clustering + ethograms post speed fix?
3. **`--motif-style trajectory`** using `maze/kpms/review_artifacts.run_similarity_matrix_csv` / `get_typical_trajectories`?
4. Global padding alternative if clusters look length-driven (`n_pad_dims` in `hdbscan_labels.csv`)?
