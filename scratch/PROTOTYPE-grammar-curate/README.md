# PROTOTYPE — grammar candidate curation preview

**Question:** When a human fills `behavior_name` on a mined n-gram row, what information do they need *before* committing — and does that name improve `is_moving` anchor agreement once exported?

**Branch:** LOGIC (state machine for curate → preview → export).

**Run:**

```bash
uv run python scratch/PROTOTYPE-grammar-curate/tui.py
# with cohort files (optional):
uv run python scratch/PROTOTYPE-grammar-curate/tui.py ^
  --candidates-csv "C:\...\behavior_ethogram\grammar\seed_042\candidate_sequences.csv" ^
  --bout-features-csv "C:\...\behavior_ethogram\stage_ii\bout_features.csv" ^
  --anchor-dir "C:\...\behavior_ethogram\anchors\is_moving\ele_v1"
```

**Delete when:** curation UX is contracted and implemented in `maze/` (or NOTES.md verdict is recorded).

See [NOTES.md](NOTES.md) for verdict placeholder.
