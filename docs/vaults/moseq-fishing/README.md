---
title: README
type: ops
assay: shared
status: na
claim_kind: na
verdict: na
tags:
  - claim/ops
  - assay/shared
---
# OpenEthoMaze claim vault (in-repo Obsidian vault)

Open this folder as a vault in Obsidian: **Open folder as vault** →

`OpenEthoMaze/docs/vaults/openethomaze`

## Layers (theory → hypothesis → estimand → estimate → verdict)

- `theories/` — T0–T4
- `hypotheses/` — H-boards
- `estimands/` + `families/` — scalars + BH family specs
- `assays/nor-impress/runs/` + `assays/vast-alz/runs/` — estimates (Runs)
- `questions/` — verdict notes (`V …`) only; score-contract stubs live in `families/`
- `shared/` — ops + [[Restructure Spec]] + [[Concordance]] + [[Litmus Ladder]] + frontmatter helper
- `attachments/` — figures
- `Prune Map.md` — lava list

## Bases (property dashboards)

- [[Claims.base]] — T/H/E/F/V by status & assay
- [[Verdicts.base]] — honesty outcomes
- [[Runs.base]] — assay runs

Hubs: [[NOR IMPRESS Index]] · [[VAST Alz Index]]

## Frontmatter

Every note carries `type`, `assay`, `status`, `claim_kind`, `verdict`, plus tags mirroring status/kind for graph colors. Re-run (idempotent skip if `---` present):

```bash
python docs/vaults/openethomaze/shared/add_frontmatter.py
```

Schema locked in [[Restructure Spec]]. Claim kinds: [[Claim Kind]]. Litmus gates: [[Litmus Ladder]]. Artifact paths: [[Artifact Linking]].

Companion prose (NOR; not a vault note): `docs/vocab/NOR-IMPRESS-OVERVIEW.md`.
