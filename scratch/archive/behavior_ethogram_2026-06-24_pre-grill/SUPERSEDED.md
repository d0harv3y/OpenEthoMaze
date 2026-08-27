# SUPERSEDED — archived 2026-06-29

This folder is the **pre-grill** behavior-ethogram planning context (dated 2026-06-24). It was archived after the 2026-06-29 grilling session because its decisions and glossary now **conflict** with the canonical context.

## Canonical replacements (live, tracked)

- Glossary: `maze/kpms/behavior_ethogram/CONTEXT.md`
- Context map: `CONTEXT-MAP.md` (repo root)
- ADRs: `docs/adr/0001-behavior-producer-agnostic-target.md`, `0002-is-moving-anchor-independent-speed.md`, `0003-bsoid-resolver-gate-and-boundary.md`

## What changed (why this conflicts)

| Pre-grill (this folder) | Superseded by |
|---|---|
| Three-stage pipeline is *the* design (ADR 0001) | Three-stage = **Option D**, one of three competing **producers** (A/B/D); `Behavior` is producer-agnostic (new ADR-0001) |
| `behavior token` / `bout cluster` are canonical terms (CONTEXT.md) | `Behavior` is the target; `behavior_token`/`merge`/`cluster_id` are **mechanisms** (new CONTEXT.md) |
| `cluster_id` as QC default + optional AR-HMM feature (ADR 0004) | Dropped `cluster_id`-as-float (only 3 clusters; categorical-as-continuous smell) |
| Mean abs Δheading only; raw syllable id dropped (ADR 0005) | Add **signed net-turn** + **tortuosity** + low-D **syllable kinematic-signature embedding**; fix circular heading (sin/cos) |
| Named behavior deferred (ADR 0009) | Naming via exemplars is **core** to Option A (discover→curate grammar) |
| Anatomical-only scope (ADR 0003) | Anatomical primary, but **Option B** (B-SOiD on pose) + cross-task generalization is the goal |

Retained for design history only. Do not cite as current.
