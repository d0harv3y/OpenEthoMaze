# Tracking v2 + multi-stream kpMS master plan

**Status:** Active plan (June 2026). Implements [h5_tracking_contract.md](h5_tracking_contract.md), enables [ethogram_scope.md](ethogram_scope.md) E0–E1 and E6, and adds a **WSL2+GPU** fit profile.

**Agent prompts:** copy-paste slices from [phase_t_agent_prompt.md](phase_t_agent_prompt.md) (tracking + kpMS streams) and [phase_wsl_agent_prompt.md](phase_wsl_agent_prompt.md) (cross-OS ops).

---

## Goals

1. **H5-first tracking** — `tracking/anatomical` + `tracking/blob` in trial HDF5; sidecars are provenance/backfill only.
2. **Three kpMS fit sources** (E6) — separate rare fits, incomparable syllable IDs:
   - **A** anatomical (`STANDARD_NODE_NAMES`, SLEAP/DLC)
   - **B** blob poly (`BLOB_NODE_NAMES`, motion-oriented 8-gon)
   - **C** fused (concatenate A+B in one `bodyparts` tensor)
3. **GPU fit on WSL2** — same codebase; Windows for DAQ/GUI, WSL for `maze-kpms-fit`.
4. **Fit speed** — subset controls + GPU + optional hyperparameter exposure; three streams multiply wall-clock (accept or defer B/C).

---

## Architecture

```mermaid
flowchart TB
  subgraph win [Windows — acquisition]
    DAQ[maze-daq] --> H5["trials.h5 v2"]
    DAQ -->|tracking/anatomical| H5
    DAQ -->|tracking/blob| H5
  end
  subgraph lib [Shared library — either OS]
    H5 --> READ[load_tracking_from_h5]
    READ --> PRE[build_kpms_inputs stream=A|B|C]
    PRE --> APPLY[maze-kpms-apply]
    APPLY --> MAT[maze-kpms-materialize]
  end
  subgraph wsl [WSL2 — GPU fit rare]
    MAN[trial_manifest.csv] --> FIT[maze-kpms-fit --pose-stream]
    PRE --> FIT
    FIT --> CKPT[checkpoint per stream]
  end
  SLP[".slp sidecar"] -.->|backfill T3 only| H5
```

---

## Phase map (dependencies)

| Phase | ID | Blocks | Delivers |
|-------|-----|--------|----------|
| Tracking schema | **T0** | — | Constants, I/O helpers, round-trip tests |
| Acquisition write | **T1** | T0 | Live anatomical + blob flush at trial `stop()` |
| kpMS read A | **T2** | T0 | `build_kpms_inputs` reads H5 anatomical; sidecar fallback |
| Backfill + UX | **T3** | T2 | Sidecar backfill; `keep_live` overwrite policy + visible UI |
| Blob orient + kpMS B | **T4a** | T1, T2 | Motion-heading vertex order; stream B preprocess |
| Fused kpMS C | **T4b** | T4a | Concat bodyparts; `--pose-stream fused` |
| Fit stream CLI | **T4c** | T2 | `--pose-stream`, separate `project_dir/<stream>/` |
| Ethogram export | **E0** | T2 | Bout CSV materialize (ethogram_scope) |
| WSL ops | **W0–W1** | T2 | Docs, paths, GPU verify, fit SOP |
| E6 spike | **T5** | T4a–c, E0 | Held-out ablation: A vs B vs C bout stability |

**Do not** start T4b/T5 until T2 gate passes. **Do not** start W1 GPU fit until W0 paths resolve.

---

## Three fit streams (E6 detail)

| Stream | `pose_stream` | K nodes | `anterior_idxs` / `posterior_idxs` | Project dir example |
|--------|---------------|---------|-----------------------------------|---------------------|
| A anatomical | `anatomical` | 8 (`STANDARD_NODE_NAMES`) | `nose` / `tail` | `kpms/anatomical/orm_kpms_fit` |
| B blob | `blob` | 8 (`BLOB_NODE_NAMES`) | derived from motion heading | `kpms/blob/orm_kpms_fit` |
| C fused | `fused` | 16 (A∥B) | nose + blob_front analogs | `kpms/fused/orm_kpms_fit` |

**Orientation (B):** Resample contour → 8 vertices; order anchored to velocity heading (unwrap); low confidence when ‖v‖ < ε. When anatomical available, optional **hint** from neck→nose vector for disambiguation — document in provenance, do not mix anatomy names into `BLOB_NODE_NAMES`.

**Syllable IDs are not comparable across streams.** Exports tag `pose_stream`; overlay picks one hypnogram layer.

**Ops:** 3× rare fit + 3× apply + 3× materialize per cohort unless lab defers B/C. Pilot with `--max-trials 50` per stream.

---

## Cross-OS development (summary)

See [phase_wsl_agent_prompt.md](phase_wsl_agent_prompt.md) for full guidance.

| Runtime | OS | Repo path | Extras |
|---------|-----|-----------|--------|
| DAQ / GUI / camera | Windows native | `C:\Users\admin\code\OpenEthoMaze` | `gui`, `sleap` |
| kpMS fit (GPU) | WSL2 Linux | **Same files** via `/mnt/c/...` or git-synced clone | `kpms` + CUDA jax |
| pytest / library | Either | Same | `dev` |

**Critical:** Do **not** maintain two divergent copies without a sync rule. Prefer **one git tree** on `/mnt/c/...` with **two `.venv`s** (Windows vs WSL), or two clones synced only via `git pull` before fit.

**Cursor:** Do not open `\\wsl.localhost\...` from the Windows side (slow, broken LSP). Use WSL extension **Reopen Folder in WSL** for Linux-native editing, or keep Windows folder open and run fit in a **WSL terminal** on `/mnt/c/Users/admin/code/OpenEthoMaze`.

---

## Agent slice index (one PR each)

| Slice | Scope | Risk | Est. files |
|-------|-------|------|------------|
| T0 | Schema + `tracking_io.py` + tests | Low | 4–6 |
| T1a | `write/read anatomical` helpers only | Low | 2–3 |
| T1b | `TrialRecorder` + `camera_loop` anatomical buffer | Medium | 3–4 |
| T1c | `blob_orient.py` + contour→8-gon | Medium | 2–4 |
| T1d | `TrialRecorder` blob flush + `backup_params_json` | Medium | 3–4 |
| T2a | `resolve_canonical_trial_h5` + `load_anatomical_from_h5` | Medium | 3–4 |
| T2b | `build_kpms_inputs` H5-first; relax `require_sleap` | Medium | 2–3 |
| T2c | Manifest/discovery `has_tracking_pose` flag | Low | 2–3 |
| T3a | `persist_pose_from_sidecar` + `keep_live` gate | Medium | 3–5 |
| T3b | Analyze dialog overwrite checkbox + status strings | Medium | 2–4 |
| T4a | `build_kpms_inputs_blob`; stream B apply/fit path | High | 4–6 |
| T4b | Fused concat stream C | Medium | 3–4 |
| T4c | `--pose-stream` on fit/apply CLI + GUI | Low | 3–5 |
| E0 | `ethogram.py` + `materialize.py` + CLI | Medium | 4–6 |
| W0 | `docs/wsl_kpms_setup.md` + `paths_local.wsl.example.py` | Low | 2–3 |
| W1 | `scripts/wsl_verify_jax_gpu.sh` + fit platform warning | Low | 2–3 |
| T5 | Spike notebook/script + findings in scratch | Research | — |

**Gate after each slice:** `uv run pytest tests/ -q` on Windows (or WSL for W slices). No GUI behavior change unless slice says so.

---

## Resolved lab decisions

- Canonical H5: acquisition `trials.h5` when controller-first; no default mirror ([h5_tracking_contract.md](h5_tracking_contract.md)).
- Pose overwrite: default **`keep_live`**; explicit user opt-in to replace with import.
- Blob **N = 8** (`BLOB_VERTEX_COUNT` in `maze/core/anatomy.py`).
- Three streams are **additional**, not replacements; combined stability is a **hypothesis** (T5 spike).

## Open decisions

1. DLC in same `tracking/anatomical` layout?
2. `tracking_source_h5` trial attr when results DB ≠ acquisition DB?
3. Refit policy across 3 streams (never / quarterly / N-new-trials threshold)?

---

## Links

- [h5_tracking_contract.md](h5_tracking_contract.md) — schema spec
- [ethogram_scope.md](ethogram_scope.md) — E0–E6 product scope
- [phase_t_agent_prompt.md](phase_t_agent_prompt.md) — agent copy-paste per slice
- [phase_wsl_agent_prompt.md](phase_wsl_agent_prompt.md) — WSL + Cursor workflow
- [rescue_plan.md](rescue_plan.md) — A–D shipped context
