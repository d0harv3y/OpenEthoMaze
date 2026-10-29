---
title: H Assay Validity NOR
type: hypothesis
assay: nor-impress
status: ladder
claim_kind: clock-portable
verdict: na
tags:
  - claim/hypothesis
  - assay/nor-impress
  - ladder
  - clock-portable
aliases:
  - Q0 Assay Validity NOR
---
# H Assay Validity NOR

**Parent:** [[T1 Recognition NOR]] (prerequisite).
**Status:** standing prerequisite. #clock-portable

---

**Question:** At recognition (`nvl_obj`), do animals show novel preference (discrimination ratio DR > 0)?

**Why it matters:** assay validity. If this fails, SD and physio stories are uninterpretable.

**Expected (lit posture):** intact controls prefer novel at recognition.

**Computed (object-prox consensus, sex=all, arms pooled):**

| Session       | DR vs 0    | Median DR (approx.) |
| ------------- | ---------- | ------------------- |
| `NOR_BL`      | hit        | ~0.17               |
| `NOR_TX`      | strong hit | ~0.47               |
| `NOR_REC3hr`  | weak       | ~0.11               |
| `NOR_REC11hr` | miss       | ~−0.05              |

**Verdict:** assay works at challenge.

## Figure

![[fig_v_assay_dr_vs0.svg]]

## Artifacts

- [[Run Object Prox DR]]
- [[Run Classic DR]]
- [[Run Protocol Prologue]]

## Related

- [[NOR IMPRESS Index]]
- [[H Novelty Preference DR]]
