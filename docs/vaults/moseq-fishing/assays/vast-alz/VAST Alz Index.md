---
title: VAST Alz Index
type: ops
assay: vast-alz
status: open
claim_kind: na
verdict: na
tags:
  - claim/ops
  - assay/vast-alz
  - open
---
# VAST Alz Index

In-repo claim map for **VAST** (virtual air-stream / vibration maze; Gerstner Alz cohort) + anatomical kpMS paramscan.

**Parallel to** [[NOR IMPRESS Index]] — separate assay / animal strata / protocol ladder. Same ladder pattern ([[Simpler-First Ladder Pattern]]), VAST runners in `scratch/vast_moseq/` (shared DA primitives live in `scratch/nor_object_mi/`).

**Campaign root:** `D:\az-sd-vast_paramscan2026\` (see [[Campaign Roots]]). Pose H5: `vast_results_legacy.h5`.

**Wire (PROTOCOL-STRATA):** `session` ∈ {`S01`…`S05`} (infer hab/exp from prefix when needed); trial ordinals → analysis **trial windows** `early_t1-3` / `mid_t4-6` / `late_t7-9`; `interval` = `run` (pass 1). Animal strata: `strain` (`wt`|`tg`) × `tx` (`RBSF-1`|`n/a`) × `sex` — concat as 4 **conditions** for stratified readout. Not NOR `condition` / `noSD`…

**Status:** living map for the paramscan2026 pack. Not a manuscript Methods section.

## Theories (fog / stub)

- [[T1 Flexibility VAST]] — condition × flexibility-linked behavior; no H yet
- [[T1 Prodromal Alz]] — placeholder until Alz NOR pose lands

## Pipeline ladder (done on disk)

1. [[Run VAST Syllable Descriptives]]
2. [[Run VAST Syllable Kinematics]]
3. [[Run VAST Syllable Signatures]]
4. [[Run VAST Trial Session Step DA]] — trial-steps + session-steps; pooled + per-condition strat volcanos

## Shared pattern (not shared strata)

- [[Simpler-First Ladder Pattern]] — the descriptives → kinematics → signatures → DA pattern both assays follow; claim links across assays go through this note only.

## Ops

- [[Campaign Roots]]
- [[Artifact Linking]]

## Vocab (repo Markdown, outside vault)

`docs/vocab/PROTOCOL-STRATA.md`, `CONTEXT.md`, `STATS.md`, `INTERPRET.md`. Campaign notes: `D:\az-sd-vast_paramscan2026\CAMPAIGN.md`.

## Graph view

Obsidian **Graph** on this folder. Color groups include this hub (see `.obsidian/graph.json`).
