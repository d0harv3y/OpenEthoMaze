# Syllable-sequence grammar contract (Option A / S3)

Schema id: **`grammar_rules_v1`**. Authority: [`maze/kpms/behavior_ethogram/grammar_contract.py`](../maze/kpms/behavior_ethogram/grammar_contract.py). Implementation: [`grammar_mine.py`](../maze/kpms/behavior_ethogram/grammar_mine.py), [`grammar_rules.py`](../maze/kpms/behavior_ethogram/grammar_rules.py), [`producer_option_a.py`](../maze/kpms/behavior_ethogram/producer_option_a.py).

**Sync rule:** candidate CSV columns and rule JSON schema are defined in `grammar_contract.py`. Contract tests: `tests/test_grammar_rule_contract.py`.

Glossary: [`maze/kpms/behavior_ethogram/CONTEXT.md`](../maze/kpms/behavior_ethogram/CONTEXT.md) (**Behavior grammar**). Output artifact: [`behavior_labeling_contract.md`](behavior_labeling_contract.md).

## Workflow (discover → curate → export)

1. **Mine** frequent bout-level syllable n-grams → `candidate_sequences.csv`
2. **Curate** — fill `behavior_name` (portable names: locomote, groom, …) using exemplar trials in `example_trial_keys`
3. **Build** `grammar_rules.json` from curated rows
4. **Export** S0 `BehaviorLabeling` to `producers/syllable_grammar/<fit_id>/`

Rules are **per-fit** (raw syllable ids are seed-specific). Only **behavior names** are portable across tasks/refits.

## Artifact locations

```
<kpms_root>/behavior_ethogram/grammar/seed_<seed>/
  candidate_sequences.csv    # mined n-grams (discover)
  grammar_rules.json         # curated rules (apply)

<kpms_root>/behavior_ethogram/producers/syllable_grammar/<fit_id>/
  behavior_frames.h5
  behavior_bouts.csv
  provenance.json
```

Path helpers: `grammar_dir`, `grammar_candidates_csv`, `grammar_rules_json`, `producer_dir(kpms_root, "syllable_grammar", fit_id)`.

## `candidate_sequences.csv`

| Column | Description |
|--------|-------------|
| `pattern_json` | JSON list of raw syllable ids, e.g. `[3, 7, 7]` |
| `pattern_len` | Pattern length in bouts |
| `count` | Total occurrences |
| `n_trials` | Distinct trials containing the pattern |
| `example_trial_keys` | Up to 5 trial keys for exemplar review (`;`-separated) |
| `behavior_name` | Curator-assigned portable name (empty until curated) |
| `notes` | Optional notes |

Patterns are **bout-level** n-grams (maximal syllable runs), not per-frame n-grams.

## `grammar_rules.json`

```json
{
  "schema": "grammar_rules_v1",
  "fit_id": "seed_042",
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
| `priority` | Tie-break when multiple rules share length (higher wins) |

## Application semantics

- Input: bout-level syllable id sequence per trial (RLE of kpMS `syllable` on aligned rows).
- Scan left-to-right; at each bout index, match the **longest** rule pattern; on length tie, higher `priority` wins.
- Matched span: every bout in the span receives the rule's `behavior_name`.
- Expand bout labels to frames via `row_start` / `row_end_exclusive` on kpMS-aligned rows → `source_frame_index`.
- Unmatched bouts / frames: `UNLABELED` (-1).

## CLIs

```bash
uv run maze-mine-syllable-grammar-candidates --kpms-root … --seed … --manifest-path …
uv run maze-build-grammar-rules --kpms-root … --seed …   # after curating CSV
uv run maze-export-syllable-grammar-labeling --kpms-root … --seed … --manifest-path …
```

Review exemplar movies: `scripts/kpms_review_artifacts.py` on `example_trial_keys`.

## Consumer rules

- Do not hard-code column lists; import from `grammar_contract.py`.
- Evaluation harness reads only the S0 producer artifact (ADR-0004), never grammar modules directly.
