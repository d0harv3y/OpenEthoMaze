# Handoff: NOR transition-structure honesty try

**Date:** 2026-10-01  
**Next session focus:** implement Family **TransStruct-A** (bout P(next | current) at recognition) and write the honesty pass.  
**Repo:** `OpenEthoMaze`  
**Claim vault:** `docs/vaults/nor-impress/`

## One-line

Grain and claim are **locked**: within sex, does `condition` change bout **transition** structure at `animal × NOR_TX × nvl_obj`? Next agent builds the runner + BH family of 4 cells — not more composition / visit-grammar fishing.

## Locked decisions (this session)

| Decision | Lock |
|----------|------|
| Primary grain | `animal × NOR_TX × nvl_obj` (recognition-linked) |
| Not primary | full-session `NOR_TX`; other sessions; BL→TX Δ — only after user OK |
| Primary scalar | `trans_dist_to_nosd_ref` (animal P vs sex-pooled noSD P) |
| Companion | `H_next_given_curr` |
| Family | **TransStruct-A** = 2 metrics × F/M = **4** Kruskal cells; `q_bh < 0.05` |
| Distinct from | [[Q5 BoutGrammar]] (nvl **visit** counts/durations — already **fail**) |

Authoritative contract: `docs/vaults/nor-impress/questions/Q5 Transition Structure Score Contract.md`  
Run stub: `docs/vaults/nor-impress/runs/Run Transition Structure.md`  
Index / Q5 board updated to point at the declaration.

## Do not relitigate

Read vault negatives; do not re-derive:

| Topic | Path |
|-------|------|
| Index / priority | `docs/vaults/nor-impress/NOR IMPRESS Index.md` |
| Q5 board | `…/questions/Q5 Condition Separating Behavior.md` |
| Engagement side claim | `…/Q5 Honesty Pass.md` |
| Visit bout grammar **fail** | `…/Q5 BoutGrammar Honesty Pass.md` |
| Composition / Shannon / DA shelf | overview + prune; treat as saturated for “condition separator” |
| Overview / strata | `docs/vocab/NOR-IMPRESS-OVERVIEW.md`, `PROTOCOL-STRATA.md` |
| Occupancy ≠ transition | `docs/vocab/INTERPRET.md` |

**Acronyms:** NOR = novel object recognition; DR = discrimination ratio; BH = Benjamini–Hochberg; kpMS = keypoint-MoSeq; MI = mutual information; BC = Bray–Curtis; DA = differential abundance.

**Data root (lab machine):** `Documents/work/sack/datas/impress/moseq_251017/_nor_object_mi/` — do not hardcode drive letters into `maze/`.

**Prior framing chats:** [Conditional sequence structure](93fa768d-39cf-435d-b1ee-8779f8f69aac); related [N-gram perplexity by strata](afab1ec9-da23-46b3-b58c-40c873af6dd1).

## Next build steps

1. Pick alphabet in the runner (portable cluster / ethogram token preferred; raw `raw_syllable_id` only with explicit methods caveat).  
2. Implement under `scratch/nor_object_mi/` (pattern: bout tables + `simpler_first_*` honesty CSVs). Lock **one** matrix distance before testing.  
3. Emit `*_per_animal.csv`, `*_tests_long.csv`, `INFO_*.md`, then `Q5 Transition Structure Honesty Pass.md`.  
4. Update Index / Q5 / Prune with pass or fail.  
5. On fail: stop — no Family B without user OK. On pass: then optional physio follow-up on **that** scalar only.

## Hooks (reference, do not reinvent contracts)

- Ethogram transitions: `docs/behavior_token_review_contract.md` → `transitions.csv`; CLI `maze-summarize-behavior-tokens`  
- Conditional MI cousin: `docs/stimulus_mi_contract.md`  
- Prior handoff style / exhausted shelf: `docs/handoffs/2026-09-23-new-compute-recognition-hunt.md`

## Suggested skills

Next agent should call the Skill tool for:

- `data-dictionary` — when writing `INFO_*.md` for the TransStruct run  
- `investigation` — only if scaffolding a longer empirical scratch folder beyond a single honesty pass  
- `obsidian-vault` — if wiring more wikilinks / graph notes after the honesty note lands  
- `tdd` — if adding reusable library math under `maze/` with litmus tests (identity / anti-identity on toy P)

## Out of scope unless user asks

- More DA / Shannon / BC atypicality as “new science”  
- Physio Spearman until TransStruct locks (or user overrides)  
- Expanding to full-session or recovery sessions after peeking at `q`  
- Alphabet-wide transition-edge fishing
