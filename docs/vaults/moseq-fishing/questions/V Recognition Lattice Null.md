---
title: V Recognition Lattice Null
type: verdict
assay: nor-impress
status: lava
claim_kind: na
verdict: fail
tags:
  - claim/verdict
  - assay/nor-impress
  - lava
aliases:
  - Q5 Recognition Honesty Pass
---
# V Recognition Lattice Null

**Date:** 2026-09-23  
**Scope:** recognition-restricted condition separators only — novelty step (`id_obj→nvl_obj`), `nvl_obj` levels / DR, object-prox fam–nvl, prox MI, DR×syllable INFO joins, session Δ on `nvl_obj`, novelty DA. Companion: [[V Engagement Delta]] (engagement Δ = non-recog side claim).  
**Gate:** Kruskal on within-animal Δ or level across `condition` within sex; consensus-animal + cross-model agreement where available; prefer `hit_fdr05` / `q_bh < 0.05`. Recognition link required (see [[H Recognition Separators]]).

## Verdict

**Fail — recognition-linked condition separation is not locked.**

Preference (DR), novelty-step Δ scalars, prox MI by condition, and DR×pause MI all miss the honesty gate at challenge (`NOR_TX`). Do **not** sell “SD impairs recognition” from these tables. Keep hunting; do not reopen physio ([[H Physio Coupling]]) on a recognition metric that does not exist yet.

**Weak / secondary only:** absolute `frac_near_nvl` level (M, `NOR_TX`) and BC recovery on `nvl_obj` (`condition→REC3hr`) — cite carefully, not as preference.

## Locked non-claims (use this)

> At `NOR_TX`, condition does **not** modulate classic or object-prox DR (Kruskal miss, both sexes). Consensus-animal novelty-step scalars (`id_obj→nvl_obj`: Δfrac_near, BC, Shannon, richness, …) have **0** `hit_fdr05` cells; per-model scalar agreement at that cell is **0/21**. Nearest-prox MI and `info_dr_pause` MI have **0** FDR hits on the condition (or association) axes audited here. Novelty DA model agreement at `NOR_TX` is **0**; BL/REC3 near-prox DA agreement is exploratory and ids are not portable (ADR-0005).

## Primary negatives (keep as negatives)

Full paths → Run hubs ([[Artifact Linking]]).

| Artifact (via Run) | Finding |
|----------|---------|
| [[Run Classic DR]] `classic_dr_tx` / `object_prox_dr_tx` | All sessions × sex: Kruskal miss on DR |
| [[Run Object Prox DR]] consensus `dr_*` × condition @ `NOR_TX` | Miss (M p≈0.96; F p≈0.34) |
| [[Run Condition on Paired Delta]] `condition_consensus_animal_condition_tests_long` step=`id_obj→nvl_obj` | **0 / 160** `hit_fdr05`; at `NOR_TX` even `hit_p05` empty for primary metrics |
| Same Run — `condition_scalar_condition_agreement` novelty @ `NOR_TX` | All metrics `frac_hit = 0` |
| Same Run — `condition_da_condition_agreement` novelty @ `NOR_TX` | `frac_model_consensus_hit = 0` (all grains/weightings/sex) |
| [[Run Nearest Prox MI]] `mi_stratum_tests_long` | `hit_fdr05` none; 3 uncorrected `hit_p05` at BL/REC11 F only |
| [[Run Info Dr Pause]] `info_dr_pause_tests_long` | No `hit_fdr05` / `hit_p05` (DR×Δp_pause MI; not a condition axis) |

**Novelty step @ `NOR_TX` (consensus animal, illustrative):** Δfrac_near M full_session frame_share p≈0.40 (medians noSD 0.083 / GHSD 0.025 / RBSD 0.024) — same miss already noted in [[V Engagement Delta]].

## Secondary / exploratory (do not elevate to #1)

| Block | Signal | Why not locked |
|-------|--------|----------------|
| Object-prox **`frac_near_nvl` level** M `NOR_TX` | Consensus Kruskal `hit_p05` (p≈0.030); **21/21** models `hit_p05`; medians ≈0.274 / 0.201 / 0.127 (noSD > GHSD > RBSD). `frac_near_fam` miss | Absolute novel-prox occupancy, **not** preference (DR still null). No BH family on this consensus table — uncorrected only. Recognition-*adjacent*, not DR impairment |
| Session **BC** `nvl_obj` `condition→REC3hr` near_0p10 M | Consensus `hit_fdr05` (q≈0.014); scalar agreement **17/21** | Composition **turnover** TX→REC3 on recognition trial — recovery/trajectory story, not contemporaneous preference at challenge |
| Novelty **DA** near_0p10 M @ BL / REC3 | Up to **16/21** model consensus | Wrong session for “challenge recognition”; median alphabet hit frac ~4–5%; raw ids not portable |
| Session Δfrac_near FDR cells (`BL→condition` id_obj M; `BL→REC11` no_obj F) | Consensus FDR | Not novelty / not `nvl_obj`-restricted preference |

## What this is / is not

| Is | Is not |
|----|--------|
| Documented **absence** of a recognition-linked condition lock on the audited lattice | Proof that SD never touches recognition biology |
| Permission to keep engagement Δ as the only honest condition separator so far ([[V Engagement Delta]]) | License to relabel engagement or BC recovery as “memory” |
| Pointer that `frac_near_nvl` level deserves a **declared** follow-up family if you want recognition-adjacent occupancy | A substitute for DR×condition |

## Keep / demote for slides

| Keep | Demote |
|------|--------|
| Explicit null panels: DR×condition @ TX; novelty-step Δfrac_near @ TX | Novelty DA volcanoes as “SD broke recognition” |
| Optional footnote: M `frac_near_nvl` level trend (uncorrected) | Prox MI / info_dr_pause as condition separators |
| Optional exploratory: BC `condition→REC3hr` `nvl_obj` near (label as recovery) | Alphabet DA at BL as challenge evidence |

## Next

Done as [[V Candidate Lattice Null]] — occupancy BH, spatial, Q4 all **fail**. Remaining #1 work needs **new** scores (quadrant / bout grammar), not re-audits of the same CSVs. Engagement Δ remains the side claim ([[V Engagement Delta]]). Physio still parked.

## Figure

Object-prox DR × condition Kruskal (consensus) — DR miss. Source: [[Run Object Prox DR]].

![[fig_v_recognition_lattice_dr_kruskal.svg]]

Condition consensus animal lattice — novelty-step empty among FDR hits. Source: [[Run Condition on Paired Delta]].

![[fig_v_recognition_lattice_condition_consensus.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[H Recognition Separators]]
- [[V Engagement Delta]]
- [[V Candidate Lattice Null]]
- [[H Novelty Preference DR]]
- [[H Assay Validity NOR]]
- [[H Investigation Quality]]
- [[Run Condition on Paired Delta]]
- [[Run Object Prox DR]]
- [[Run Classic DR]]
- [[Run Nearest Prox MI]]
- [[Run Info Dr Pause]]
- [[Run Session Paired]]
- [[Prune Map]]
- [[NOR IMPRESS Index]]

#lava
