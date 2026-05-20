# Scripts

Batch tools live in the installed package as **`maze.cli`** modules. Run them with **`uv run maze-<name>`** (see `pyproject.toml` `[project.scripts]`).

| Console command | Module |
|-----------------|--------|
| `maze-legacy-db` | `maze.cli.legacy_db` |
| `maze-render-trial-overlay` | `maze.cli.render_trial_overlay` |
| `maze-render-ram-trial-overlay` | `maze.cli.render_ram_trial_overlay` |
| `maze-reprocess-controller-h5` | `maze.cli.reprocess_controller_h5` |
| `maze-trial-summary-dictionary` | `maze.cli.trial_summary_data_dictionary` |
| `maze-kpms-review-artifacts` | `maze.cli.kpms_review_artifacts` |
| `maze-kpms-apply-syllable-merge` | `maze.cli.kpms_apply_syllable_merge` |
| `maze-kpms-clean-syllable-bouts` | `maze.cli.kpms_clean_syllable_bouts` |
| `maze-kpms-build-training-exemplar-table` | `maze.cli.build_kpms_training_exemplar_table` |
| `maze-generate-selected-trials-nor-kpms` | `maze.cli.generate_selected_trials_from_nor_kpms_results` |
| `maze-overlay-slp-bout` | `maze.cli.overlay_slp_bout_pipeline` |
| `maze-export-ram-trial-manifest` | `maze.cli.export_ram_trial_manifest_csv` |
| `maze-fix-ele-h5-session-animal-ids` | `maze.cli.fix_ele_h5_session_animal_ids` |
| `maze-sleap-nn-batch-inference` | `maze.cli.sleap_nn_batch_inference` |
| `maze-langfuse-demo` | `maze.cli.langfuse_demo` |

Files in this directory with the same names are **thin shims** so `uv run python scripts/foo.py` still works after `uv sync`; they delegate to `maze.cli` and do not modify `sys.path`.

**`archive/`** — frozen legacy scripts (ruff excluded); not installed as entry points.
