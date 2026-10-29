# Wayfinder map: DR-framed motion sequencing deck

Labels: `wayfinder:map`

## Destination

Ship a **lab-internal dense PPTX** (now **6** slides) that reframes NOR+SD motion sequencing through **discrimination ratio (DR) and fam|nvl constituents**, plus a matching vault report under `docs/vaults/moseq-fishing/`. Spine: (1) assay+clock collinearities, (1b) COUNT/UNCERTAINTY formula table, (2) composition DR ladder incl. Hill2, (3) session-steps, (4) can/cannot + composition-in-recognition gloss, (5) future clocks / B-SOiD / SSL (`lightly`). Done when the deck and vault note exist and cite only locked figures (existing or newly built join boards).

## Notes

- **Domain:** IMPRESS NOR + kpMS; nouns from `docs/vocab/` (CONTEXT, STATS, FORMULAS, INTERPRET, PROTOCOL-STRATA).
- **Execution override:** this map carries build (runners/figs/PPTX/vault), not plan-only.
- **Audience:** lab-internal. PPT has **no** vault wikilinks, levity tags, or honesty-pass jargon.
- **Locked scope:** 0.10 m prox only (no quadrant ROI); session-steps only (no trial-steps); no per-animal alphabet story; exemplar model `paramscan_s1-1e7_s2-3e4_ss-100` with light cross-model consensus mention.
- **Pause syllable:** use the exemplar raw syllable that maps into cross-model `cluster_id` 13 — **`raw_syllable_id` 5** on that model (do not center the slide on cluster13 branding).
- **Composition DR cousins:** richness → Shannon → Hill q=2 (**include**; per-scalar families locked). Clinical relevance **unknown — show, don't sell**; slide 4 may hint Shannon as bits to describe syllable occupancy proportions near fam vs nvl.
- **Future directions (slide 5):** alternate clocks; B-SOiD; SSL (leJEPA, DINO, SimCLR) pointing at `C:\Users\admin\code\lightly` — not in-deck compute.
- **Skills:** grilling, domain-modeling, publication-figures, data-dictionary, obsidian-vault; vocab spine.
- **Tracker:** local markdown (`.scratch/dr-framed-motion-seq-deck/`).

## Decisions so far

- [Destination and slide budget](issues/00-destination-locked.md): finished PPTX+vault; **5** dense slides; classic investigation DR ↔ `dr_time_prox` headline; classic↔object-prox twin; still↔exemplar pause syll5; composition through DR lens without stealing assay headline.
- [Uncertainty suite for composition DR](issues/02-uncertainty-suite-inventory.md): sealed Family A = shannon+richness; **hill2/dominance already figured** in `simpler_first_prox_quad_comp_figs_min0` via `prox_comp.py` + `fig_prox_quad_comp_violins.py` — no new runner.
- [Exemplar pause syllable assets (syll 5)](issues/03-exemplar-pause-syllable-assets.md): syll5 GIF/Δp/share exist; still↔pause join board still missing (inputs join; ρ≈0.80 on share). Brand syll5/pause, not cluster13.
- [Include Hill q=2 / dominance on the deck?](issues/04-include-hill-dominance.md): **show hill2**; re-ran condition with **one BH family per scalar** → [[V ProxComp Per-Scalar Null]] (assay pass; 0 FDR in Shannon/Richness/Hill2 families).
- [Lock five slide claim sentences](issues/01-slide-claim-sentences.md): merged assay+collinearities; Hill2 on composition slide; session-steps yes; conclusions + composition gloss; future clocks/B-SOiD/SSL.
- [Join board figure contracts](issues/05-join-board-contracts.md): build A+C+D; reuse B; **exemplar model** raw alphabet (not cluster panels); syll5 level-share vs frac_still.
- [Session-step panel choice](issues/06-session-step-panel-choice.md): rebuild prox shannon/richness/hill2 session-steps on exemplar; one session_paired time twin; no trial-steps.
- [Build missing join boards](issues/07-build-join-boards.md): A/C/D/E/F built under `simpler_first_dr_framed_deck_exemplar/`; vault [[Run DR Framed Deck Exemplar]]. Classic↔time ρ=0.94; still↔syll5 ρ=0.80; richness collinear, shannon/hill2 not.
- [Ship PPTX and vault report](issues/08-ship-pptx-and-vault.md): 5-slide PPTX + [[Motion Sequencing DR Framed Report]]; Index wired.

## Not yet specified

- (none — destination shipped; polish layout inches only if a human reopens.)

## Out of scope

- Per-animal kpMS fit vs pooled alphabet story.
- Quadrant ROI analysis.
- Trial-step lattices.
- Full Q5 recognition hunt / engagement-Δ treasure / physio primary screens (thin context only).
- Regenerating the 60-slide hunt deck.
- Boss-facing polish beyond lab-internal density.
