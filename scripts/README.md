# Scripts

Batch tools live in the installed package as **`maze.cli`** modules (or **`maze.kpms`** for cohort fit/apply). Run them with **`uv run maze-<name>`** (see `pyproject.toml` `[project.scripts]`).

| Console command | Module | Extras |
|-----------------|--------|--------|
| `maze-legacy-db` | `maze.cli.legacy_db` | core |
| `maze-render-trial-overlay` | `maze.cli.render_trial_overlay` | core |
| `maze-render-ram-trial-overlay` | `maze.cli.render_ram_trial_overlay` | core |
| `maze-reprocess-controller-h5` | `maze.cli.reprocess_controller_h5` | core |
| `maze-trial-summary-dictionary` | `maze.cli.trial_summary_data_dictionary` | core |
| `maze-kpms-review-artifacts` | `maze.cli.kpms_review_artifacts` | `kpms` |
| `maze-kpms-apply-syllable-merge` | `maze.cli.kpms_apply_syllable_merge` | `kpms` |
| `maze-kpms-clean-syllable-bouts` | `maze.cli.kpms_clean_syllable_bouts` | `kpms` |
| `maze-kpms-build-training-exemplar-table` | `maze.cli.build_kpms_training_exemplar_table` | `kpms` |
| `maze-kpms-fit` | `maze.kpms.fit` | `kpms` |
| `maze-kpms-apply` | `maze.kpms.apply` | `kpms` |
| `maze-generate-selected-trials-nor-kpms` | `maze.cli.generate_selected_trials_from_nor_kpms_results` | `kpms` |
| `maze-overlay-slp-bout` | `maze.cli.overlay_slp_bout_pipeline` | core |
| `maze-export-ram-trial-manifest` | `maze.cli.export_ram_trial_manifest_csv` | core |
| `maze-fix-ele-h5-session-animal-ids` | `maze.cli.fix_ele_h5_session_animal_ids` | core |
| `maze-sleap-nn-batch-inference` | `maze.cli.sleap_nn_batch_inference` | `sleap` |
| `maze-langfuse-demo` | `maze.cli.langfuse_demo` | optional Langfuse env |
| `maze-daq` / `maze-ram-daq` | acquisition `__main__` | `gui` |
| `maze-local-service` | `local_service.__main__` | `local-service` |

**Canonical:** `uv run maze-<name>` after `uv sync` (and extras as noted).

**Shims:** Root `scripts/*.py` delegate to the modules above (`uv run python scripts/<name>.py`). Prefer console scripts for new automation.

**`demos/`** — non-production examples ([demos/README.md](demos/README.md)). Langfuse demo is **not** at `scripts/` root.

**`archive/`** — frozen legacy (ruff/black excluded); not installed as entry points.

## Classification (maintained / promoted / archive)

Per [docs/rescue_plan.md](../docs/rescue_plan.md) § Scripts classification.

| Verdict | Path / command | Notes |
|---------|----------------|-------|
| **Promoted** | `maze-reprocess-controller-h5` | `maze/cli/reprocess_controller_h5.py` + `scripts/reprocess_controller_h5.py` shim |
| **Promoted** | `maze-export-ram-trial-manifest` | `maze/cli/export_ram_trial_manifest_csv.py` + shim |
| **Promoted** | `maze-kpms-fit`, `maze-kpms-apply` | `maze/kpms/fit.py`, `maze/kpms/apply.py` + shims (same code as GUI workers) |
| **Maintained (shim)** | `legacy_db.py` → `maze-legacy-db` | Cohort DB init/sync/run |
| **Maintained (shim)** | `render_trial_overlay.py`, `render_ram_trial_overlay.py` | Unified overlay MP4 |
| **Maintained (shim)** | `trial_summary_data_dictionary.py` | Trial summary schema export |
| **Maintained (shim)** | `kpms_*.py`, `build_kpms_training_exemplar_table.py`, `generate_selected_trials_from_nor_kpms_results.py` | kpMS review/merge/clean/helpers (`--extra kpms`) |
| **Maintained (shim)** | `overlay_slp_bout_pipeline.py` | SLP bout overlay pipeline |
| **Maintained (shim)** | `fix_ele_h5_session_animal_ids.py` | One-off H5 ID repair |
| **Maintained (shim)** | `sleap_nn_batch_inference.py` | Batch SLEAP-NN (`--extra sleap`) |
| **Demo** | `demos/langfuse_demo.py` → `maze-langfuse-demo` | Langfuse trace demo; not for production pipelines |
| **Frozen** | `archive/**` | Legacy one-offs; do not extend or install |

### Frozen `archive/` (reference only)

| File | Role |
|------|------|
| `init_db.py`, `sync_db.py` | Superseded by `maze-legacy-db` |
| `run_pipeline.py`, `run_exports.py` | Superseded by `maze-legacy-db run` / exports |
| `render_overlay_video.py` | Superseded by `maze-render-trial-overlay` |
| `sleap_nn_inference_oldVAST.py` | Superseded by `maze-sleap-nn-batch-inference` |
| `verify_sleap_nodes.py`, `debug_qc_trial.py`, `fix_zero_frame_videos.py` | Lab one-offs |
| `oldarchive/*` | Historical validation / QC scripts |

**Do not** add features under `scripts/archive/` (ruff/black excluded by design).
