# Syllable-sequence grammar contract (Option A / S3)

Schema id: **`grammar_rules_v1`**. Authority: [`maze/kpms/behavior_ethogram/grammar_contract.py`](../maze/kpms/behavior_ethogram/grammar_contract.py). Implementation: [`grammar_mine.py`](../maze/kpms/behavior_ethogram/grammar_mine.py), [`grammar_rules.py`](../maze/kpms/behavior_ethogram/grammar_rules.py), [`producer_option_a.py`](../maze/kpms/behavior_ethogram/producer_option_a.py).

**Sync rule:** candidate CSV columns and rule JSON schema are defined in `grammar_contract.py`. Contract tests: `tests/test_grammar_rule_contract.py`.

Glossary: [`maze/kpms/behavior_ethogram/CONTEXT.md`](../maze/kpms/behavior_ethogram/CONTEXT.md) (**Behavior grammar**, **anchor_bucket**). Output artifact: [`behavior_labeling_contract.md`](behavior_labeling_contract.md).

> **S3.1 curation:** enrich at mine, `anchor_bucket` + overlay review gates at build, `behavior_anchor_buckets` on rules JSON and S0 provenance. See [§ Curation workflow](#curation-workflow-s31).

## Workflow (discover → curate → export)

1. **Mine** frequent bout-level syllable n-grams → `candidate_sequences.csv`
2. **Curate** — assign `behavior_name`, `anchor_bucket`, review stamps; exemplar overlay on `example_trial_keys` when `must_review_overlay=1`
3. **Build** `grammar_rules.json` from curated rows
4. **Export** S0 `BehaviorLabeling` to `producers/syllable_grammar/<fit_id>/`
5. **Evaluate** — `maze-evaluate-behavior-producers` vs `is_moving` anchor (reads S0 provenance only)

Rules are **per-fit** (raw syllable ids are seed-specific). Only **behavior names** are portable across tasks/refits.

## Artifact locations

```
<kpms_root>/behavior_ethogram/grammar/seed_<seed>/
  candidate_sequences.csv    # mined n-grams (discover; lean curation table)
  candidate_exemplars.json   # review exemplars keyed by pattern_json
  grammar_rules.json         # curated rules (apply)

<kpms_root>/behavior_ethogram/producers/syllable_grammar/<fit_id>/
  behavior_frames.h5
  behavior_bouts.csv
  provenance.json
```

Path helpers: `grammar_dir`, `grammar_candidates_csv`, `grammar_candidate_exemplars_json`, `grammar_rules_json`, `producer_dir(kpms_root, "syllable_grammar", fit_id)`.

## Mining parameters (current code)

| Parameter | Default | CLI flag | Notes |
|-----------|---------|----------|-------|
| **max pattern length** | **4 bouts** | `--max-n` | Mines n-grams for n = 1 … max_n inclusive |
| min occurrences | 5 | `--min-count` | Patterns with `count < min_count` dropped |
| example trials | 5 keys | — | `example_trial_keys` capped per row |

Bout-level only: each element of a pattern is one **syllable bout** (maximal run of identical kpMS `syllable` labels), not a per-frame n-gram.

## Candidate list ranking (mine output)

Rows in `candidate_sequences.csv` are sorted by:

1. **`count` descending** (more occurrences first)
2. **`pattern_len` descending** (longer patterns before shorter at equal count)
3. **`pattern` lexicographic** (stable tie-break)

**Subset patterns are not deduplicated.** If `[3]` and `[3, 7, 7]` both meet `min_count`, both appear as separate rows. A shorter pattern is often a **subset** of a longer one; mine does not collapse or hide subsets.

### Curating subset / superset patterns

Two different ranking systems apply:

| Phase | What wins | Purpose |
|-------|-----------|---------|
| **CSV sort** (discovery) | High `count`, then long `pattern_len` | What to look at first when naming |
| **Apply** (`label_bouts_with_grammar`) | **Longest match** at each bout index, then `priority` | What actually labels trials |

**Apply semantics (current code):**

- Scan bout sequence left → right.
- At index `i`, consider rules ordered by **(-pattern length, -priority, pattern)**.
- First matching rule wins; advance `i` by the matched span length.
- Shorter rules only label bouts where no longer rule matched at that position.

**Example:** rules `groom → [3,7,7]` and `locomote → [3]`. A bout stream `… 3,7,7,3,3 …` labels the first three bouts `groom`; isolated `3` bouts later can still become `locomote`.

**Curation guidance:**

1. Name **specific** behaviors on **long** patterns first (`[3,7,7]` → `groom`).
2. Use **short** patterns for **broad** defaults (`[12]` → `pause`) knowing longer rules take precedence wherever they overlap.
3. Do **not** expect CSV row order to match apply precedence — build sets `priority = len(pattern) * 10` when compiling rules from candidates.
4. **Same `behavior_name` on subset and superset** is allowed (e.g. both `locomote`) but redundant; prefer one rule per behavior unless you need disjoint contexts.
5. **Conflicting names on nested patterns** (e.g. `[3]`→`locomote`, `[3,7,7]`→`groom`) is the intended grammar-with-memory shape — apply resolves by longest match, not by CSV rank.

**Planned (S3.1, not implemented):** optional `is_subsumed` column or mine filter to hide pattern `P` when a longer pattern with similar trial coverage exists — for curator UX only; apply would still use explicit rules.

## `candidate_sequences.csv`

| Column | Description |
|--------|-------------|
| `pattern_json` | JSON list of raw syllable ids, e.g. `[3, 7, 7]` |
| `pattern_len` | Pattern length in bouts |
| `count` | Total occurrences |
| `n_trials` | Distinct trials containing the pattern |
| `mean_speed_mps`, `mean_abs_dheading`, `mean_straightness`, `mean_blob_area_px2` | Pooled bout scalars from `stage_ii/bout_features.csv` (auto at mine when file present) |
| `mean_duration_s` | Pooled mean per-bout duration (s) over **all** matched bouts |
| `mean_distance_m` | Pooled mean per-bout path length (m), derived as `bout_mean_speed_mps * bout_duration_s` |
| `mean_iqr_speed_mps` | Pooled mean of per-bout speed IQR (m/s) |
| `mean_heading_rad` | Pooled **circular** mean of per-bout mean heading (rad); requires `bout_mean_heading_rad` in `bout_features.csv` (compile with `--include-heading-direction`) |
| `must_review_overlay` | `1` if exemplar movie required before naming |
| `behavior_name` | Curator-assigned portable name (empty until curated) |
| `anchor_bucket` | `moving` \| `still` \| `ignore` — harness tag (per **behavior_name**, validated at build) |
| `reviewed_at` | ISO timestamp after overlay review |
| `reviewed_trial_key` | Which exemplar trial was watched |
| `preview_grid_path` | Relative path to exemplar grid MP4, back-filled by `maze-preview-grammar-candidate-grid` |
| `notes` | Optional notes |

Pooled scalar means (including the new columns) are computed over **every** matched bout in the corpus for the seed, not just the capped `example_trial_keys`. Exemplar spans in `candidate_exemplars.json` are selected to spread across **animals then sessions then trials** (ranked by non-ambiguous + closeness to the pooled mean speed), so a candidate's preview grid does not collapse onto one animal/session.

Overlay gate (`must_review_overlay=1`) when **any** of: bout `ambiguous=1` on a matching bout; mean speed in gray zone (~0.06–0.14 m/s); low speed + high mean \|dheading\|.

### `candidate_exemplars.json` (S3.2 sidecar)

Verbose review data lives outside the CSV. Schema: `grammar_candidate_exemplars_v1`. Keys are `pattern_json` strings; values hold `example_trial_keys` and `example_matches` (max **3** bout-span exemplars per pattern):

```json
{
  "schema": "grammar_candidate_exemplars_v1",
  "fit_id": "seed_042",
  "patterns": {
    "[3, 7, 7]": {
      "example_trial_keys": ["1-S01-T01", "1-S01-T02"],
      "example_matches": [
        {
          "trial_key": "1-S01-T01",
          "bout_start_index": 4,
          "bout_end_exclusive": 7,
          "row_start": 120,
          "row_end_exclusive": 185,
          "source_start_frame": 4500,
          "source_end_frame": 4620
        }
      ]
    }
  }
}
```

Populated at mine when `stage_ii/bout_features.csv` is present. Selection prefers non-ambiguous spans, diverse trials, and speeds near the row’s pooled mean. Legacy CSV columns are still read as a fallback by `maze-preview-grammar-candidate`.

Preview one or more matches:

```bash
uv run maze-preview-grammar-candidate \
  --kpms-root … --seed … --manifest-path … --pipeline-h5 … \
  --row-index 0 --match-index 0 --out …/grammar_review/

# comma-separated match indices (writes one MP4 per index when --out is a directory)
uv run maze-preview-grammar-candidate … --row-index 42 --match-index 2,3,4,5,6,7 --out …/grammar_review/

# N random distinct matches (optional --match-seed for reproducibility)
uv run maze-preview-grammar-candidate … --row-index 42 --random-matches 6 --match-seed 0 --out …/grammar_review/
```

Clips the overlay to the match span ± 1 s (default) using `clip_source_start_frame` / `clip_source_end_frame` on the unified overlay renderer.

## `grammar_rules.json`

```json
{
  "schema": "grammar_rules_v1",
  "fit_id": "seed_042",
  "behavior_anchor_buckets": {"groom": "ignore", "pause": "still", "locomote": "moving"},
  "rules": [
    {"pattern": [3, 7, 7], "behavior_name": "groom", "priority": 30},
    {"pattern": [12], "behavior_name": "pause", "priority": 10}
  ]
}
```

| Field | Description |
|-------|-------------|
| `pattern` | Non-empty list of raw syllable ids (this fit only) |
| `behavior_name` | Portable behavior label assigned to matching bout span |
| `priority` | Tie-break when multiple rules share **length** (higher wins) |
| `behavior_anchor_buckets` | Map behavior_name → `moving` \| `still` \| `ignore` (derived at build; copied to S0 provenance on export) |

## Application semantics

- Input: bout-level syllable id sequence per trial (RLE of kpMS `syllable` on aligned rows).
- Scan left-to-right; at each bout index, match the **longest** rule pattern; on length tie, higher `priority` wins.
- Matched span: every bout in the span receives the rule's `behavior_name`.
- Expand bout labels to frames via `row_start` / `row_end_exclusive` on kpMS-aligned rows → `source_frame_index`.
- Unmatched bouts / frames: `UNLABELED` (-1).

## Curation workflow (S3.1)

Grill decisions (2026-06-30):

| # | Decision |
|---|----------|
| Q1 | `behavior_name` (ethology) **+** `anchor_bucket` (`moving`/`still`/`ignore`) |
| Q2 | Buckets in `grammar_rules.json` → S0 `provenance.json` `behavior_anchor_buckets`; harness reads artifact only |
| Q3 | Auto-enrich scalars at **mine**; exemplar overlay **required** for flagged rows |
| Q4 | Auto `must_review_overlay` from ambiguous + speed gray-zone + low-speed/high-dheading |
| Q5 | One `anchor_bucket` per `behavior_name`; build fails on conflict |
| Q6 | `reviewed_at` + optional `reviewed_trial_key` on candidate CSV |
| Q7 | **Document first** — this section — before S3.1 code |

**Operational loop:**

1. `maze-mine-syllable-grammar-candidates` (optionally `--max-n`, `--min-count`)
2. Join / review scalars; sort by `must_review_overlay` then `count`
3. `maze-preview-grammar-candidate` on `example_matches_json` for flagged rows → stamp `reviewed_at` / `reviewed_trial_key`
4. Fill `behavior_name`, `anchor_bucket`
5. `maze-build-grammar-rules` (enforces review + bucket consistency; `--force` skips overlay gate)
6. `maze-export-syllable-grammar-labeling`
7. `maze-evaluate-behavior-producers` vs `anchors/is_moving/<calibration_id>/`

**Harness tie-in:** Only behaviors with `anchor_bucket` ∈ `{moving, still}` score against `is_moving`. `ignore` (e.g. `groom`, `rear`) exports normally but is excluded from agreement. Harness reads `behavior_anchor_buckets` from S0 provenance (fallback: hardcoded name lists in `evaluate.py`).

**Pose vs scalars:** kpMS syllable ids encode egocentric pose; bout scalars encode locomotion/blob summaries. Scalars help disambiguate speed-overlapping classes; **overlay exemplars** are required for pose-shaped distinctions (groom vs rear) when scalars agree.

Prototype TUI: [`scratch/PROTOTYPE-grammar-curate/`](../scratch/PROTOTYPE-grammar-curate/README.md).

## CLIs

```bash
uv run maze-mine-syllable-grammar-candidates --kpms-root … --seed … --manifest-path … [--max-n 4] [--min-count 5] [--bout-features-csv …] [--no-enrich]
uv run maze-preview-grammar-candidate --kpms-root … --seed … --manifest-path … --pipeline-h5 … --row-index 0 --out …/
uv run maze-build-grammar-rules --kpms-root … --seed … [--force]   # after curating CSV
uv run maze-export-syllable-grammar-labeling --kpms-root … --seed … --manifest-path …
uv run maze-evaluate-behavior-producers --anchor-dir …/is_moving/ele_v1 --producer-dir …/syllable_grammar/seed_042
```

Review exemplar movies: `scripts/kpms_review_artifacts.py` or `maze-render-trial-overlay` on `example_trial_keys`.

## Consumer rules

- Do not hard-code column lists; import from `grammar_contract.py`.
- Evaluation harness reads only the S0 producer artifact (ADR-0004), never grammar modules directly.
