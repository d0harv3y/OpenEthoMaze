# NOR IMPRESS — boss `NOR#` → wire `session`

**Scope: NOR IMPRESS only.** Do **not** reuse this map for VAST, RAM, other NOR labs, or future assays. Other datasets need their own local export notes.

Wire columns stay `session` / `trial` / `condition` ([PROTOCOL-STRATA.md](PROTOCOL-STRATA.md)). Boss tokens (`NOR1` … `NOR4`) are **not** columns in new work — map once at ingest, keep the boss string in `original_session` (or equivalent) for audit.

## Source of truth (upstream)

| Role | Path |
|------|------|
| Remap rules | `archive/IMPRESS/my_nor_wip/utils/session_naming.py` → `_remap_session_type_by_rules` |
| Cohort / sex / condition | `archive/IMPRESS/my_nor_wip/config.py` → `ANIMAL_INFO` (`cohort`, `sex`, `tx` → wire `condition`) |
| Worked example export | `archive/IMPRESS/my_nor_wip/exports/nor_trial_manifest.csv` |

OpenEthoMaze scratch helper (same rules, IMPRESS-named on purpose):  
`scratch/nor_object_mi/impress_nor_boss_session.py`

## Boss day → wire `session`

Always (all cohorts):

| Boss prefix | Wire `session` |
|-------------|----------------|
| `NOR1` | `NOR_BL` |
| `NOR2` | `NOR_TX` |

Cohort-dependent recovery:

| Boss prefix | Cohort | Wire `session` |
|-------------|--------|----------------|
| `NOR3` | `exp1`, `exp3p1` | `NOR_REC3hr` |
| `NOR3` | `exp3p2` | `NOR_REC11hr` |
| `NOR4` | `exp1` | `NOR_REC11hr` |

`exp2` has no `NOR3` / `NOR4` in the IMPRESS layout.

Raw keys look like `NOR1_nvl_obj`; boss-only labels in some kpMS manifests are `NOR1` with trial implied by the video.

## Boss / filename → wire `trial`

| Boss / filename cue | Wire `trial` | Prose gloss |
|---------------------|--------------|-------------|
| `*_no_obj` / `No OBJ` | `no_obj` | acclimation |
| `*_id_obj` / `ID OBJ` | `id_obj` | familiarization |
| `*_nvl_obj` / `NVL OBJ` | `nvl_obj` | recognition |

Legacy export cells may still say `novel_obj` / `identical_obj` — normalize to `nvl_obj` / `id_obj` on write.

## Animal strata (from `ANIMAL_INFO`)

| Config field | Wire column | Values |
|--------------|-------------|--------|
| `tx` | `condition` | `noSD` \| `GHSD` \| `RBSD` |
| `sex` | `sex` | `M` \| `F` |
| `cohort` | `cohort` (optional audit) | `exp1` \| `exp2` \| `exp3p1` \| `exp3p2` |

## kpMS recog fit note (`moseq_recog_260915`)

That sweep’s selected trials are **recognition only** (`trial=nvl_obj`), but **across** boss days present for each cohort (including recovery `NOR3`/`NOR4` where they exist) — not BL+TX alone, and not habituation / `no_obj` / `id_obj`.
