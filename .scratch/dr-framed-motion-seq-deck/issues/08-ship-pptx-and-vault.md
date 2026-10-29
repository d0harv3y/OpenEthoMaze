# Ship PPTX and vault report

Type: task
Status: resolved
Blocked by: 01, 06, 07

## Question

(Unblocking task.) Assemble the 5-slide lab-internal PPTX and vault report from locked claims + figures.

Defaults (override when claimed):

- PPTX: `C:\Users\admin\Documents\work\davis lab\Motion sequencing NOR - DR framed.pptx`
- Vault: `docs/vaults/moseq-fishing/assays/nor-impress/Motion Sequencing DR Framed Report.md` + Index wire-in
- PPT: no vault refs / levity tags; define NOR, SD, kpMS, DR once on title slide
- Exemplar model mentioned; consensus mentioned lightly

## Answer

Settled 2026-10-09.

| Deliverable | Path |
|-------------|------|
| PPTX (5 slides) | `C:\Users\admin\Documents\work\davis lab\Motion sequencing NOR - DR framed.pptx` (~3.9 MB) |
| Builder | `scratch/nor_object_mi/build_dr_framed_motion_seq_deck.ps1` (PowerPoint COM) |
| Vault report | [[Motion Sequencing DR Framed Report]] |
| Join boards | [[Run DR Framed Deck Exemplar]] |

Slide map: (1) assay+clocks A/B/C; (2) composition E richness/Shannon/Hill2; (3) session-step F + G `frac_near`; (4) can/cannot + D scatters; (5) clocks / B-SOiD / SSL.
