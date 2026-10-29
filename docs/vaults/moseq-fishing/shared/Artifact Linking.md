---
title: Artifact Linking
type: ops
assay: nor-impress
status: na
claim_kind: mixed
verdict: na
tags:
  - claim/ops
  - assay/nor-impress
  - mixed
---
# Artifact Linking

**Rule:** claim notes answer questions; **Run** notes own disk paths; `INFO_*.md` beside campaign folders stay the data dictionaries — do not paste column tables into the vault ([[README]]).

## Link graph (preferred)

```
H  →  F  →  E
       ↓
      Run  →  campaign folder + key files + figures + runner
       ↓
      V
```

| From | Link to artifacts via |
|------|------------------------|
| Hypothesis `H` | Wikilink **Runs** / **Families** / **Verdicts** — not raw sack paths |
| Family `F` | `[[Run …]]` § Artifacts (one line); optional member `E` |
| Estimand `E` | `[[Run …]]` that produced the scalar + `F` |
| Verdict `V` | `[[Run …]]` + **required `## Figure`** supporting the claim (Obsidian `![[attachments/…]]` embed preferred; else portable link via Run § Figures) |
| Run | **Campaign root** (under [[Campaign Roots]]), file table, **Figures** table, runner path, `F`/`E`/`V`/`H` |

Claim **kind** (`#clock-portable` vs `#alphabet-bound`) lives on H / V / report rows — see [[Claim Kind]].

## Run note — Artifacts section template

```markdown
## Links
- Family: [[F …]]
- Estimands: [[E …]] · …
- Verdict: [[V …]]
- Hypothesis: [[H …]]
- Claim kind: #clock-portable and/or #alphabet-bound (if the Run is mixed, say so)

## Artifacts
**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/<folder>/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `*_per_animal.csv` | D — per-animal scalars |
| `*_tests_long.csv` | I — Kruskal + BH family |
| `INFO_*.md` | Data dictionary (authoritative columns) |
| `run_summary.json` | Knobs + pass/fail |

### Figures
| File | Role | Claim kind |
|------|------|------------|
| `figures/fig_….svg` | human-facing panel | #clock-portable or #alphabet-bound |
| vault `attachments/fig_….svg` | optional Obsidian embed copy | (same) |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/<script>.py`
```

Paths stay **portable** (`sack/…`, `OpenEthoMaze/scratch/…`). Lab absolute drives belong only in [[Campaign Roots]] footnotes if needed.

### Figures — where they live

| Place | When |
|-------|------|
| Campaign `figures/` (+ `FIGURES.md` if present) | Authoritative — owned by the Run |
| `sack/.../vault_verdict_figures/` | Auto honesty panels for null families (`fig_vault_verdict_panels.py`) |
| Vault `attachments/` | Copies needed for Obsidian `![[…]]` embeds on **every** V |
| Verdict `## Figure` | **Required** — one (or few) panels that support the locked claim language |

Do **not** scatter figure paths across H / F / E. Do **not** invent a Family for a figure pack.

## What not to do

- Duplicate INFO column dictionaries inside vault claim notes
- Scatter the same sack path across H / F / E / V without a Run hub
- `file:///` links to D: (break on other machines; prefer Campaign Roots + relative path)
- Mint `F …` notes for V&V / collinearity / alphabet-equating slide decks ([[Claim Kind]])

**Exception:** [[Prune Map]] stays a **folder-level** keep/demote inventory (with Run wikilinks in the Why column). Do not treat prune rows as claim-card artifact sections.

## Related

- [[Campaign Roots]] · [[Claim Kind]] · [[Restructure Spec]] · [[NOR IMPRESS Index]]
