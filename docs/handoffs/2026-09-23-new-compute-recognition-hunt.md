# Handoff: new-compute recognition hunt (NOR IMPRESS Q5)

**Date:** 2026-09-23  
**Next session focus:** implement **new** recognition-linked condition-separating scores (not re-audit existing CSVs).  
**Repo:** `OpenEthoMaze`  
**Claim vault:** `docs/vaults/nor-impress/` (start at `NOR IMPRESS Index.md`)

## One-line

Shelf recognition / occupancy / Q4 / spatial audits all **fail** honesty gates; only locked condition separator is male object-appearance engagement Δ (non-recognition). Next work must **define + compute** per-animal geometry or bout-grammar scores, declare a BH family, then Kruskal by condition.

## Do not relitigate

Authoritative negatives and side claim live in the vault — read, do not re-derive from scratch:

| Note | Path |
|------|------|
| Index / priority | `docs/vaults/nor-impress/NOR IMPRESS Index.md` |
| Engagement side claim (keep) | `docs/vaults/nor-impress/questions/Q5 Honesty Pass.md` |
| Recognition lattice fail | `…/Q5 Recognition Honesty Pass.md` |
| Candidates fail (occupancy BH, spatial D-only, Q4) | `…/Q5 Candidates Honesty Pass.md` |
| Q5 status board | `…/Q5 Condition Separating Behavior.md` |
| DR×condition null | `…/Q1 Condition Effect on DR.md` |
| Physio parked | `…/Q2 Honesty Pass.md` |
| Prune / demote | `docs/vaults/nor-impress/Prune Map.md` |
| Overview | `docs/vocab/NOR-IMPRESS-OVERVIEW.md` |
| Vocab / stats | `docs/vocab/{CONTEXT,STATS,FORMULAS,INTERPRET,PROTOCOL-STRATA}.md` |

**Acronyms:** NOR = novel object recognition; DR = discrimination ratio; BH = Benjamini–Hochberg FDR; kpMS = keypoint-MoSeq; Q5 = condition-separating behavior question.

**Data root (lab machine):** `Documents/work/sack/datas/impress/moseq_251017/_nor_object_mi/` (do not hardcode drive letters into `maze/` library code).

**Priorities (lab):** (1) recognition-linked condition separator → (2) physio only after lock → (3) Q4 as tool for (1). Do not reopen physio fishing.

## What “new compute” means

Already exhausted without new runners:

- Novelty-step Δ / DA / DR / prox MI / info_dr_pause  
- Declared `frac_near_nvl`/`fam` BH Family A (M uncorrected p≈0.03 → q≈0.12)  
- Classic `t_nvl_s` investigation family; four-mask TX−BL×condition  
- Spatial heatmaps = **descriptive only** (pooled; no per-animal I)

**Build one of these (prefer in order):**

### A. Per-animal quadrant / side-mass (primary ask)

- Grain: `animal × session × nvl_obj` (sex-stratified Kruskal by `condition`).  
- Align like heatmaps: fam-left via rot180 (`scratch/nor_object_mi/syllable_spatial_heatmap.py` already has arena bbox / rot180 / fam–nvl loci).  
- Candidate scalars (pick **few**, declare family before testing):
  - fraction of session (or near-object) frames in **nvl-side** half / quadrant  
  - dwell seconds or frame share in nvl vs fam quadrant  
  - optional: distance-to-midline signed bias  
- **Not** DR in disguise: avoid `(nvl−fam)/(nvl+fam)` rebrand; if you compute share, say so and keep DR as separate known-null.  
- Output: `*_per_animal.csv` + `*_tests_long.csv` + `INFO_*.md` + BH family table.  
- Honesty: `hit_fdr05` within declared family; consensus across models if kpMS-dependent.

### B. Bout grammar near novel (Q4-shaped)

- Upstream bouts: `ladder_bout_features.csv` / `bout_kinematics.py` (`bout_mean_dist_fam_m`, `bout_mean_dist_nvl_m`, …).  
- Candidate scalars: mean/median bout duration in nvl prox (r=0.10 m), approach–leave count, still-near fraction **per animal** (four_mask is TX−BL ANOVA — different design; do not confuse).  
- Same honesty gate as A. Portable definition; no raw `raw_syllable_id` as primary (ADR-0005).

### C. Out of scope unless user asks

- Re-cutting `condition_on_paired_delta` / object_prox consensus for more p-hacks  
- Physio Spearman until a metric locks  
- Per-animal kpMS fit before a quality litmus  
- ARRIVE methods polish  

## Suggested first build step

1. Write a short **score contract** in vault (`Q5` or new `Run …` stub): formula, grain, family size, hit rule.  
2. Implement runner under `scratch/nor_object_mi/` (pattern: `simpler_first_object_prox.py` + INFO skill).  
3. Run on `moseq_251017`; write honesty note; update Index / Q5 / Prune.  
4. Only if FDR locks: optional engagement-companion slide; then physio follow-up on **that** scalar.

## Code / artifact hooks

- Spatial alignment helpers: `scratch/nor_object_mi/syllable_spatial_heatmap.py`  
- Fam/nvl roles: `scratch/nor_object_mi/fam_nvl.py`  
- Object-prox precedent (metrics + Kruskal + consensus): `scratch/nor_object_mi/simpler_first_object_prox.py`  
- Engagement slide (side claim only): `scratch/nor_object_mi/fig_q5_engagement_delta_slide.py` → vault `attachments/fig_q5_engagement_delta_nor_tx_{m,f}.svg`  
- Install: `uv sync` / extras per `AGENTS.md` — do not ad-hoc pip  

## Suggested skills (next agent)

Call **Skill tool** / Read these before coding:

1. **`data-dictionary`** (`C:\Users\admin\.cursor\skills\data-dictionary\SKILL.md`) — `INFO_<tag>.md` for the new run.  
2. **`investigation`** (`C:\Users\admin\.cursor\skills\investigation\SKILL.md`) — if framing as a scratch investigation folder rather than only vault notes.  
3. **`tdd`** (`C:\Users\admin\.agents\skills\tdd\SKILL.md`) — litmus tests for the score (identity / known toy geometry) before cohort Kruskal.  
4. **`writing-for-agents`** — only if extending vault / AGENTS prose for the new runner.  
5. Repo vocab rules already in always-applied: `composition-vocab`, `markdown-math` (chat = Unicode; `FORMULAS.md` = KaTeX).

Skip: Bugbot / security / PR skills unless user asks to ship a PR.

## Success criteria for next session

- [x] Named score ≠ DR, ≠ total locomotion, ≠ engagement Δ rebrand — `frac_nvl_side` / `mean_signed_x_m`  
- [x] Declared BH family **before** looking at q — Family SideMass-A (16) in `Q5 SideMass Score Contract.md`  
- [x] Artifacts + INFO on disk; vault honesty note linked from Index / Q5  
- [x] Explicit pass/fail — **FAIL** (`Q5 SideMass Honesty Pass.md`); stopped (no Family B)

**Follow-up (if user OK):** bout grammar (option B), not SideMass re-cuts.

### Option B status (2026-09-23)

- [x] BoutGrammar-A declared + computed + honesty — **FAIL** (`Q5 BoutGrammar Honesty Pass.md`)
- Stopped; no Family B on visit scores without user OK
