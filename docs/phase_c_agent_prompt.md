# Phase C agent prompt (copy into a new Cursor chat)



Use when continuing **Phase C — Product narrative** on OpenEthoMaze.



---



## Prompt — Phase C complete (h5web optional)



**Use when core + C8/C9 are done and `uv run pytest tests/ -q` is green.** h5web long-lived service is optional (rescue_plan v1.1).



```

Implement Phase C from docs/rescue_plan.md. Scope Phase C only.



## Done in repo



- C7 provenance, C1 Discovery, C2 Virtual acquisition, C3 Analyze prefilter, C6 treatment labels CSV

- C4 kpMS fit: `run_kpms_fit`, `KpmsFitRunConfig`, `kpms_fit_dialog.py`, Pipeline → kpMS fit…

- C5 kpMS apply: `run_kpms_apply`, `KpmsApplyRunConfig`, `kpms_apply_dialog.py`, Pipeline → kpMS apply…

- C8 QC summary: `qc_summary.py`, `qc_summary_dialog.py`, Pipeline → QC summary…

- C9 Overlay: `overlay_dialog.py`, `run_unified_overlay`, Pipeline → Render unified overlay…



## Optional



- h5web via long-lived service (rescue_plan v1.1)



## Tests



uv sync --extra dev && uv run pytest tests/ -q

```



---



## Prompt — Phase C complete (after ALL tasks + pytest green)



**Use only when C5, optional slices, and full test suite are green with no open debug failures.**



```

Phase C (Product narrative) for OpenEthoMaze is complete. Fix regressions only.



## Shipped pipeline (GUI)



Discover → Virtual acquisition → Analyze → (kpMS fit → kpMS apply) → Export



| Step | Menu | Backend |

|------|------|---------|

| Discover | Discovery… | sync_discovery_into_h5, treatment_labels create/open |

| Pose | Virtual acquisition… | get_backend("sleap_nn"), skip-existing |

| Analyze | Analyze… | prefilter_mode=controller |

| Fit | kpMS fit… | run_kpms_fit, provenance |

| Apply | kpMS apply… | manifest CSV, apply_summary.json |

| QC | QC summary… | mistrial_summary.csv + action hints |

| Overlay | Render unified overlay… | `maze-render-trial-overlay` |

| Export | Export… | existing |

| Observe | — | provenance/*.json |



## Extras



- gui, sleap (inference), kpms (fit/apply), local-service (ORM subprocess)



## Verify



uv sync --extra dev && uv run pytest tests/ -q



## Next



- Phase D: main_window split, AGENTS.md — docs/rescue_plan.md

- Phase E: ethogram — docs/ethogram_scope.md

```



---



## Notes



- [rescue_plan.md](rescue_plan.md) lab checklist per PR.

- Ethogram E0 parallel track: [ethogram_scope.md](ethogram_scope.md).

