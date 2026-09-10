# Protocol strata

Shared wire names for within-animal protocol structure across **NOR** (novel object recognition), **VAST** (virtual air-stream / maze), and **RAM** (radial-arm maze / EHRAM). Companion to [CONTEXT.md](CONTEXT.md) (composition nouns). Hard rename: **no dual columns**.

## Voice

**Wire / code / DB / CSV columns**: `session`, `trial`, `interval`, plus animal strata (`condition`, `sex`, …).  
**Discuss / plan (optional gloss)**: *stage* ≈ session, *phase* ≈ trial — **prose and figures only**, never column names or filenames.  
**Implement**: short assay tokens; capitalize letters in tokens only when they are acronyms (`noSD`, `GHSD`, `RBSD`, `TX`).

## Protocol ladder (within-animal)

Ordered coarse → fine:

**Session**:
One same-day visit / protocol-day instance for an animal.
_Avoid_: phase, stage (as column names); treatment (for the day label)

**Trial**:
One within-session task unit. NOR trials vary object setup; VAST/RAM trials are ordinals with no task-parameter variation yet.
_Avoid_: phase, condition (as column names); session

**Interval**:
One within-trial segment of the recording.
_Avoid_: phase, band (ephys Hz), bare iti as the live name

Wire values for **interval**: `run` | `wait`.

## Animal strata (not on the ladder)

Between-animal (or animal-level) labels that stratify analyses. Same home as sex / strain / drug — **not** rungs of session → trial → interval.

**Condition**:
Sleep-deprivation (or related) arm assigned to the animal.
_Avoid_: tx, TX (as column name), treatment, treatment_group

Wire values (normalize on write): `noSD` | `GHSD` | `RBSD`.

Other animal strata (unchanged roles): `sex`, `strain`, `drug`.

## Assay value grammars

### NOR

| Column | Wire values | Optional prose gloss |
|--------|-------------|----------------------|
| `session` | `NOR_BL`, `NOR_TX`, `NOR_REC3hr`, `NOR_REC11hr` | baseline; **challenge**; 3 h recovery; 11 h recovery |
| `trial` | `no_obj`, `id_obj`, `nvl_obj` | acclimation; familiarization; recognition |
| `interval` | `run`, `wait` (when used) | — |
| `condition` | `noSD`, `GHSD`, `RBSD` | no SD; gentle-handling SD; rotary-bar SD |

`NOR_TX` and RAM `TX` are the same **challenge** idea (same condition arms).

### VAST

| Column | Wire values | Notes |
|--------|-------------|--------|
| `session` | `H##`, `S##` | Habituation vs experimental **inferred from prefix** (`H*` / `S*`). No separate hab\|exp column. |
| `trial` | `T##` | Ordinal; no object-setup variation. |
| `interval` | `run`, `wait` | Replaces MI/ethogram misuse of `phase` for run/iti. |
| `condition` | assay-specific arms (e.g. project labels) | Replaces `tx` / `treatment`. |

### RAM

| Column | Wire values | Optional prose gloss |
|--------|-------------|----------------------|
| `session` | `train_1`, `train_2`, `train_3`, `TX`, `RECOV` | training days; **challenge**; recovery |
| `trial` | `T##` | Ordinal. |
| `interval` | `run`, `wait` (when used) | — |
| `condition` | `noSD`, `GHSD`, `RBSD` | Same arms as NOR. |

H5 paths remain `/{animal}/{session}/{trial}` conceptually; **campaign B does not rewrite historical H5 groups**.

## Cutover

| Campaign | Scope | Status |
|----------|--------|--------|
| **B** (first) | `vocab/` + rule pointer; OpenEthoMaze live schema/docs/exports; NOR scratch + `_nor_object_mi` analysis CSVs/code (columns + identifiers). Figure **stems** can wait. | Done (stems moved to C) |
| **C** (second) | sack `curatedbehavior` and other published long CSVs; stem sweeps as needed. | Mostly done — see below |
| **Later** | On-disk H5 group/attr migration — prefer one **ultra-legacy** read-only merge. Sketch: [docs/tickets/unified-ultra-legacy-h5.md](../tickets/unified-ultra-legacy-h5.md). | Deferred sketch |

### Campaign C progress

**Done**

- `datas/curatedbehavior`: NOR long (`treatment group`/`phase layer`/`condition layer` → `condition`/`session`/`trial`; object tokens); sofia (`TX`/`phase`/`condition` → `condition`/`session`/`trial`); EHRAM metrics + pilot; PD `TX`→`condition` (+ `PD_condition_assignments.csv`); VAST trial_summary `treatment`→`condition`, `iti_wait`→`wait`; mistrial drop `phase`; legacy manifest `tx`→`condition` / drop `phase`.
- OEM `scratch/nor_object_mi` module stems: `_tx_`→`_condition_`, `phase_paired`→`session_paired`.
- Sack `_nor_object_mi` artifact file stems + `INFO_*.md` / small CSV cell strings (`novel_obj`→`nvl_obj`, grain `phase`→`session`, etc.).
- OEM stimulus MI + behavior-token dictionaries/contracts: `interval` + `condition`; token-summarize CSV column `interval`.
- Vocab `STATS.md` / `CONTEXT.md` / `INTERPRET.md` grain examples aligned.

**Deferred**

- Vendor raw PD trial CSVs under `LE FRAG SLEEP/` (not assignment table).
- Very large long CSVs (`da_syllable_deltas_*`, etc.) if any residual prose remains in cells (headers already clean; skipped for size).
- On-disk H5 group/attr migration (**Later**).
## Legacy → current

### Column / field renames

| Old | Current | Where |
|-----|---------|--------|
| `phase_layer` | `session` | NOR analysis |
| `condition_layer` | `trial` | NOR analysis |
| `tx`, `TX`, `treatment`, `treatment_group` | `condition` | manifests, exports, NOR |
| `treatment_labels.csv` | `condition_labels.csv` | repo `inputs/` + output_dir templates |
| `phase_step` (BL→TX…) | `session_step` | NOR paired steps |
| VAST manifest `phase` (`habituation`\|`experimental`) | *(dropped)* | infer from `session` prefix |
| MI / ethogram `phase` (`run`\|`iti`) | `interval` | stimulus MI, `_run`/`_iti` consumers |
| RAM CSV/H5 label `phase` (`train_*`, `SD`, `RECOV`) | `session` | EHRAM / trial_ns |
| ORM abuse: `session`←NOR phase_layer, `trial`←condition_layer | already the right *roles*; fix **values** to current tokens | old NOR→ORM export |

### Value renames / normalization

| Old | Current |
|-----|---------|
| `identical_obj` | `id_obj` |
| `novel_obj` | `nvl_obj` |
| `id_obj` / `nvl_obj` / `no_obj` | *(unchanged — preferred)* |
| step strings with `identical` / `novel` | use `id_obj` / `nvl_obj` |
| `iti`, `iti_wait`, file suffix `_iti` | `wait` (interval) |
| `NoSD` | `noSD` |
| RAM session `SD` | `TX` |
| NOR boss aliases `NOR1` / `NOR2` | map per local export notes onto `session` (often BL vs TX) — do not revive as columns |

### Optional prose only (not columns)

| Gloss | Means wire |
|-------|------------|
| stage | `session` |
| phase | `trial` |
| challenge | `session` ∈ {`NOR_TX`, `TX`} |
| acclimation / familiarization / recognition | NOR `trial` `no_obj` / `id_obj` / `nvl_obj` |
| baseline / 3 h recovery / 11 h recovery | NOR `NOR_BL` / `NOR_REC3hr` / `NOR_REC11hr` |
| SD session *(legacy phrase)* | prefer **challenge**; old RAM `SD` → `TX` |
