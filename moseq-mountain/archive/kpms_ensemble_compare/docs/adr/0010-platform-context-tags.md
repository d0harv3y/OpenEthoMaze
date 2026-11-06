# ADR 0010: Task-agnostic pose labels + generalized context tags

## Status

Accepted (2026-06-22, platform correction)

## Context

OpenEthoMaze is a multi-task platform (VAST open field, RAM radial maze, NOR planned). Early ontology text was RAM-centric (arms, object investigation). Pose ethology should transfer across tasks; spatial semantics differ by apparatus.

## Decision

- **Pose labels** (Phase II–III): task-agnostic where possible (`freeze`, `groom`, `walk`, `sniff`, …).
- **Context tags**: separate orthogonal dimensions — `apparatus`, `trial_epoch`, `zone`, `spatial_epoch`, optional `zone_id`.
- **Task-specific pipeline metrics** (arm entry, object investigation, dwell regions) map into general tags via per-apparatus config (e.g. `context_tags_ram.yaml`), not as canonical export column names.
- Label expansion stays on the [ONTOLOGY.md](../ONTOLOGY.md) roadmap; Phase IIIa scope unchanged (still-tier freeze/groom).

## Consequences

- Bout/frame export schema should reserve context columns even when only VAST or RAM is deployed today.
- NOR can add `zone=object_vicinity` without renaming pose labels.
- Block ethograms and test2 ensemble work remain valid; wording shifts from “maze-only” to platform.

## Alternatives considered

- **Per-task ethograms:** Duplicate pose ontology; harder to compare treatments across apparatus.
- **RAM-specific pose names (`arm_explore` as behavior):** Conflates pose with geometry.
