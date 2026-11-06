# Behavioral ethogram — candidate ontology

Reference for Phase II–III naming. Not all labels are detectable with current features; see **Detectability** column.

**Platform context:** OpenEthoMaze supports multiple **apparatus tasks** (today: **VAST** circular open field, **RAM** radial-arm maze; **NOR** planned). **Pose ethology** (freeze, groom, walk, …) should be **task-agnostic**. **Context tags** describe where/when in the trial — use a **general schema** with task-specific zone maps.

**Sensors:** Top-view pose (SLEAP) + blob. Pipeline exports **ambulation & exploration** metrics per task (dwell, arms, objects, …) — join as context, don’t re-derive inside kpMS.

**Lab precedent (kpMS / open field):**

| Source | Named categories |
|--------|------------------|
| [Datta et al., Nature Methods 2024](https://www.nature.com/articles/s41592-024-02318-2) — open field | **Categories:** rearing, grooming, walking; **within-category:** turn angle, speed (~25 syllables) |
| Same paper — benchmark vs human labels | **Locomotion, rearing, face grooming, body grooming** (4-class) |
| [kpMS docs — analysis](https://keypoint-moseq.readthedocs.io/en/latest/analysis.html) | Manual syllable naming after grid movies; merge similar syllables into groups |
| Recent stress/FC + kpMS preprint (bioRxiv 2025) | **Freezing, sniffing, grooming, turn, locomotion, climbing, jump** + unassigned/mixed |

**Design principle (our ADRs):** kpMS syllables ≈ **motifs** (pose dynamics). Ethogram **names** ≈ **merged groups of tokens**. **Context tags** are orthogonal columns (zone, epoch, apparatus) joined from pipeline geometry — not synonyms for pose labels.

---

## Layer 1 — Phase II locomotion tiers (kinematic, unnamed)

Already locked. Assign from anatomical token scalars only.

| Tier | Kinematic gist |
|------|----------------|
| `still` | Very low speed, low heading change |
| `slow_explore` | Low–moderate speed, meandering heading |
| `fast_transit` | High speed, relatively straight |
| `turn_heavy` | Moderate speed, high heading change rate |
| `ambiguous` | Failed bout-coherence QC |

---

## Layer 2 — Phase III coarse ethology (task-agnostic pose)

Appropriate **first expansion** beyond freeze/groom. Same labels across VAST, RAM, and future NOR unless apparatus makes a pose rare (e.g. rearing in top view). Map multiple tokens → one name after QC.

| Label | Ethological gist | Detectability now | Phase | Notes |
|-------|------------------|-------------------|-------|-------|
| **freeze** | Global immobility, risk assessment | ★★★ speed + blob still | IIIa | vs groom via anatomical–blob contrast |
| **groom** | Self-groom (face/body) | ★★★ contrast + clips | IIIa | Start merged; split face/body in IIIb if clips support |
| **sniff** / **investigate** | Head-down, low displacement, active nose | ★★ pose shape + low speed | IIIb | Datta benchmark separates grooming from locomotion; sniff often merged with slow explore without head keypoints |
| **rear** | Vertical posture | ★ top-view weak | IIIb | Common in OF papers; may be rare or merged into `stretch` from your camera |
| **walk** | Steady locomotion | ★★★ slow/fast tiers | IIIb | Rename tier + heading filter |
| **turn** / **pivot** | In-place reorientation | ★★★ turn_heavy tier | IIIb | |
| **sprint** / **run** | Fast straight locomotion | ★★★ fast_transit tier | IIIb | |
| **stretch-attend** | Long body, low speed, not groom | ★★ pose shape | IIIb | OF “risk assessment” family |
| **dig** | Repetitive forepaw motion | ★ pose + context | defer | If substrate digging exists in apparatus |
| **jump** / **startle** | Brief high-accel burst | ★★ accel spike | IIIb | ELS paper used jump; needs short bout detection |
| **mixed** / **transition** | Syllable boundary artifact or blend | QC | IIIb | Keep — kpMS papers retain unassigned frames |
| **unassigned** | Noisy tracking or unclear | QC | IIIb | |

---

## Layer 3 — Context tags (platform; spatial join)

**Do not** name these from kpMS alone. Join pose token/tier time series with pipeline geometry and trial state. Use **general tag names** in exports; map task-specific detectors in a small config per apparatus.

### General schema (columns on frame or bout)

| Dimension | Purpose | Example values |
|-----------|---------|----------------|
| `apparatus` | Which task / geometry contract | `vast`, `ram`, `nor` |
| `trial_epoch` | Trial phase from legacy state | `run`, `iti`, `habituation`, … |
| `zone` | Normalized spatial region | `center`, `periphery`, `wall_adjacent`, `arm`, `platform`, `object_vicinity`, `neutral` |
| `spatial_epoch` | Pipeline-defined bout type | `exploration`, `investigation`, `dwell`, `arm_visit`, `transition` |
| `zone_id` | Optional disambiguator | `arm_3`, `object_A`, `quadrant_NE` |

Pose label + context = interpretable ethogram row, e.g. `groom` during `trial_epoch=iti`, or `sniff` during `spatial_epoch=investigation` + `zone=object_vicinity`.

### Task → zone / epoch mapping (illustrative)

| Apparatus | Pipeline source | Maps to general tags |
|-----------|-----------------|----------------------|
| **VAST** (circular OF) | Dwell grids, xy vs arena radius | `zone=center` \| `periphery` \| `wall_adjacent`; `spatial_epoch=dwell` |
| **VAST** | Thigmotaxis / exploration bouts | `spatial_epoch=exploration` |
| **RAM** | Arm entry / exploration metrics | `zone=arm` + `zone_id`; `spatial_epoch=arm_visit` \| `exploration` |
| **RAM** | Central platform | `zone=platform` |
| **NOR** (future) | Object investigation bouts | `zone=object_vicinity` + `zone_id`; `spatial_epoch=investigation` |

Task-specific metric names stay in pipeline CSVs; ethogram exports use **general** `zone` / `spatial_epoch` where possible.

---

## Layer 3b — Legacy task-specific names (avoid in platform exports)

Use only in per-task docs or mapping configs — not as the canonical ethogram column names.

| Task-specific (legacy) | Prefer general tag |
|------------------------|-------------------|
| `arm_entry` / `arm_explore` | `spatial_epoch=arm_visit`, `zone=arm` |
| `object_investigation` | `spatial_epoch=investigation`, `zone=object_vicinity` |
| `thigmotaxis` | `zone=wall_adjacent` + exploration epoch |
| `center_explore` vs `periphery` | `zone=center` \| `periphery` |

---

## Expanded hypothesis table (still behaviors + neighbors)

For Phase IIIa QC and Phase IIIb expansion.

| Pattern | Anatomical speed | Blob speed | Heading / pose | Fused agrees? | Candidate label |
|---------|------------------|------------|----------------|---------------|-----------------|
| Global still | very low | very low | compact | yes | **freeze** |
| Local motion, low centroid | low–moderate | very low | periodic head motion | yes | **groom** |
| Low speed, head extended down | low | low–moderate | head-down shape | partial | **sniff** / **investigate** |
| Low speed, elongated body | low | low | body extension | partial | **stretch-attend** |
| Moderate speed, meander | moderate | moderate | turning | — | **slow_explore** / **walk** |
| High speed, straight | high | high | low turn rate | — | **sprint** |
| Moderate speed, high turn rate | moderate | moderate | high dθ | — | **turn** |
| Brief accel spike | spike | spike | any | — | **jump** |
| Investigation epoch (spatial join) | low | low | head-down | — | pose: **sniff**; context: `spatial_epoch=investigation` |
| Arm visit epoch (spatial join) | varies | varies | — | — | pose: tier; context: `spatial_epoch=arm_visit` |
| Center vs periphery (VAST) | varies | varies | — | — | context: `zone=center` \| `periphery` only |
| Token QC fail | — | — | — | no | **ambiguous** |
| Clip unclear | — | — | — | — | **unsure** (reviewer) |

---

## Recommended naming order

1. **IIIa:** `freeze` | `groom` | `other_still` | `unsure` — still-tier tokens only.
2. **IIIb (locomotion):** map `slow_explore`, `fast_transit`, `turn_heavy` tiers → `walk`, `sprint`, `turn`.
3. **IIIb (posture):** `sniff`, `stretch-attend`, `rear` where pose-shape features (ADR 0002 C-later) + clips support.
4. **IIIb (context):** attach generalized `apparatus`, `trial_epoch`, `zone`, `spatial_epoch` from pipeline joins — orthogonal to pose label. Per-task mapping in `context_tags_{apparatus}.yaml` (future).

---

## What to avoid

- **15+ pose names on day one** — Datta used ~25 syllables but only **~4–7 merged categories** for biology.
- **Renaming speed_index as ethology** — rank ≠ behavior.
- **freeze = `is_moving==0`** — debounced spot speed (ADR 0002).
- **RAM-only column names** (`arm_entry`) in platform bout CSV — use general `zone` / `spatial_epoch` + mapping config.
- **Duplicating pipeline bout detectors** inside kpMS — join existing metrics as context.
