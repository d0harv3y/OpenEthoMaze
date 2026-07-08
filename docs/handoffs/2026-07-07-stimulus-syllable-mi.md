# Handoff: stimulus to syllable join + stimulus-conditioned MI

Date: 2026-07-07. Mode when written: plan approved, no code yet.

## What this is

New pilot analysis. Question: does animal's response to VAST run-stimulus differ by sex / genotype / tx? Operationalized as mutual information between per-bout stimulus state and syllable behavior, per animal, tested across groups.

Plan is authoritative. Do NOT re-derive it here. Read:
`.cursor/plans/stimulus_syllable_mi_a29cf8bb.plan.md` (data flow, 3 stages, contracts, todos).

## Decisions already locked (from grill session, don't relitigate)

- Grain = per-bout (RLE syllable run), not per-frame.
- Stimulus vars = BOTH delivered duty (`feedback/table.motor_fb`) AND distance (`xy.dist_to_exit_px`), side by side. Divergence = saturation effect.
- MI = BOTH occupancy `I(syll;stim)` and transition `I(next_syll;stim|cur_syll)`.
- Inference = per-animal MI, Miller-Madow bias-corrected. Group test = Mann-Whitney/Kruskal on the per-animal distribution (no pseudoreplication). NOT mixed-model for this pilot.
- Factors = sex + genotype + tx. Genotype = `strain` col, already clean wt/tg in `inputs/treatment_labels.csv` (NOT free-text as earlier feared; verified).
- Cohort scope = config-driven CLI filters, defaults `experiment in {VASTcont,VASTalt}`, drop `?`/blank strain+sex. LAST excluded. tx passthrough.
- Phase = run + iti BOTH. iti = negative control (fixed duty -> MI must be ~chance; flag if not).
- Bins = global fixed quantile edges across filtered cohort. Report per-animal H(stim) alongside.
- Nulls = BOTH circular time-shift (primary, conservative) + bin-label permutation (loose bound), n_perm=1000.



## Key code anchors (verified this session)

- Stimulus persisted per-frame: `motor_fb` in `FEEDBACK_ROW_DTYPE`, `dist_to_exit_px` in `XY_ROW_DTYPE` -> `maze/core/schema.py`.
- Duty formula: `TrialStateMachine.duty_for_position` -> `maze/controller/acquisition/vast/trial_flow.py` ~line 340. Linear in distance, clamped, `min_at_exit=True` (loud far, quiet at exit).
- Bout RLE: `syllable_runs` -> `maze/kpms/behavior_ethogram/bout_scalars.py:22`.
- Frame alignment: `KpmsAlignmentCache` / `source_frame_indices` -> `maze/kpms/frame_alignment.py`. Bout `row_start/row_end_exclusive` index kpMS rows; map to frames via source_frame_indices (pattern: `bout_kinematics.trial_state_for_rows:93`).
- Existing bout table to enrich: `stage_ii/bout_features.csv`, fields `BOUT_TABLE_FIELDS` -> `maze/kpms/behavior_ethogram/bout_feature_contract.py:42`.
- Phase split: `bout_in_phase` -> `maze/kpms/behavior_ethogram/behavior_token_summarize.py:62`.
- CLI/alignment reference impl: `maze/cli/mine_syllable_grammar_candidates.py:128-146`.
- `scipy>=1.7` already declared (`pyproject.toml:12`). No new deps needed.



## Hard caveat to carry into every output

Stimulus = deterministic function of distance-to-exit -> MI cannot separate "responds to signal" from "responds to goal proximity". No probe/omission trial exists. habituation/iti control + duty-vs-distance divergence are partial checks only. Say this in results, not just code.

## First action for next agent

Todo `verify_h5`: read one VASTcont + one VASTalt trial H5, confirm `feedback/table.motor_fb` path + `dist_to_exit_px` populated for THIS cohort before writing the reader. Legacy VAST imports may only carry a W/M feedback series (`feedback.py write_feedback_series`) -> different provenance. Check.

## Not done

No files written. All 8 todos in plan pending. No cohort data validated.

## Suggested skills

- `tdd` -> synthetic tests first (monotone map -> MI>0, independent -> ~null, flat -> ~0).
- `diagnose` / `verify-this` -> if iti negative control fails or MI looks too high (bias/autocorrelation).
- `domain-modeling` -> if new terms crystallize (was active during planning; CONTEXT.md not yet created).

