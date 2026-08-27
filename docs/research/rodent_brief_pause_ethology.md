# Rodent brief pause / stillness ethology — Research Notes

**Question:** Which peer-reviewed rodent (mouse/rat) video or pose/keypoint studies discuss a **brief pause**, **micro-pause**, **hesitation**, **stop-and-go**, **immobility bout**, **stillness**, **pausing**, brief/non-fear **freeze**, **arrest**, **halt**, or similar motif — something analogous to OpenEthoMaze **cluster 13** (kpMS pause/still-like syllables: long, slow, crooked bouts) in NOR / open-field / ethogram work?

**Sources:** Primary literature (ethograms, MoSeq/keypoint-MoSeq, pose ethograms, motor-arrest circuit papers, intermittent-locomotion ecology, sleep-deprivation / video-sleep proxies). Compiled 2026-08-26; sleep-deprivation (SD) pass added 2026-08-27.

---

## Summary verdict

A real ethological motif exists — **short, non-fear inactivity interrupting locomotion or exploration** — but it is **fragmented across vocabularies**. Classical ethograms sometimes split **pausing** from **freezing** by duration (e.g. &lt;3 s vs &gt;3 s). MoSeq/keypoint-MoSeq (kpMS) routinely recover **pause syllables** as sub-second kinematic motifs. Circuit work separates **pause-and-play motor arrest** from **defensive freezing**. Ecology treats **intermittent locomotion pauses** as vigilance/search trade-offs.

**Closest literature match to cluster 13 is kinematic/descriptive (MoSeq “pause” syllables; ethogram “pausing”/“standstill”), not a validated NOR cognitive construct.** Novel Object Recognition (NOR) papers almost never score “hesitation pauses” as a primary endpoint; they score object investigation time. Assigning function to cluster 13 (vigilance, appraisal, motor hold, rest, or DA-driven stillness) requires local evidence beyond the syllable label.

**Sleep deprivation (SD) does not supply a ready named match.** SD papers discuss stillness heavily (microsleeps; ≥40 s video-sleep proxies; quiet wake; coarse open-field / FST immobility), but they do **not** score Takahashi-style pausing, MoSeq pause syllables, standstill, or motor arrest as a standard SD ethogram item. Association with SD is therefore **indirect** (sleep pressure → more quiet/immobile time) rather than motif-specific.

Evidence is **moderate for existence of the motif**, **thin for a single shared name**, **weak for NOR-specific functional claims**, and **weak for a direct SD↔brief-pause ethology link**.

---

## What “our cluster 13” is (local context)

In this repo, **cluster 13** is an HDBSCAN `cluster_id=13` over kpMS syllable prototypes, labeled **pause/still-like**, described as **long, slow, crooked bouts**. It appears as a treatment-pooled differential abundance (DA) winner on the NOR_TX novelty step; analyses live under `scratch/nor_object_mi/` (e.g. `cluster13_tx_delta.py`, crowd movies of sampled bouts). This note does **not** re-derive that DA claim — it only maps the motif to external ethology.

---

## Terminology map

| Term | Typical operational meaning | Typical context | Primary anchors |
|------|-----------------------------|-----------------|-----------------|
| **Freezing** | Absence of all visible movement except respiration; often tense posture / defensive state | Fear conditioning, predator odor, threat | Fanselow tradition; BehaviorDEPOT cites Fanselow/Bolles ([Gabriel et al., 2022](https://doi.org/10.7554/elife.74314); [Fanselow & Bolles, 1979](https://doi.org/10.1037/h0077609)) |
| **Pausing** (ethogram) | Brief inactivity, explicitly **shorter** than freezing | Open field; multi-item ethogram | Takahashi/Koide: pausing = inactivity **&lt;3 s**; freezing = stationary **&gt;3 s** ([Takahashi et al., 2006](https://doi.org/10.1007/s10519-005-9038-3); [MPD Koide3](https://phenome.jax.org/projects/Koide3)) |
| **Immobility** | Catch-all: little/no locomotion; may still allow grooming/head motion depending on threshold | Tracking software, OFT, FST | ANY-maze FAQ distinguishes immobility (user threshold) from freezing (no movement except respiration) |
| **Standstill** | Framewise ethogram class: animal not locomoting; often separated from **local exploration** | Depth/RGB-D OFT annotation | [Gerós et al., 2020](https://doi.org/10.3758/s13428-020-01381-9) |
| **Pause syllable** (MoSeq) | Unsupervised motif with near-zero pose change / low velocity; sub-second timescale typical | Depth MoSeq / kpMS open field, pharmacology | [Wiltschko et al., 2015](https://doi.org/10.1016/j.neuron.2015.11.031); [Wiltschko et al., 2020](https://doi.org/10.1038/s41593-020-00706-3); [Weinreb et al., 2024](https://doi.org/10.1038/s41592-024-02318-2) |
| **Quiescence** | Coarse ethogram bucket for low-movement states | B-SOiD post hoc labeling | [Hsu & Yttri, 2021](https://doi.org/10.1038/s41467-021-25420-x) |
| **Motor arrest / pause-and-play** | Global hold of ongoing motor program; resume from same phase; **not** vlPAG freezing | Optogenetics + video/EMG; natural 0.5–2 s OF arrests | [Goñi-Erro et al., 2023](https://doi.org/10.1038/s41593-023-01396-3) |
| **Intermittent locomotion pause** | Brief stop between locomotor bouts during travel | Field ecology (sciurids); video of travel paths | [McAdam & Kramer, 1998](https://doi.org/10.1006/anbe.1997.0592); [Kramer & McLaughlin, 2001](https://doi.org/10.1093/icb/41.2.137) |
| **Rest / inactive-but-awake** | Heterogeneous inactivity; affective meaning depends on form/context | Welfare reviews | [Fureix & Meagher, 2015](https://doi.org/10.1016/j.applanim.2015.08.036) |
| **Microsleep** | Brief involuntary sleep intrusion into wakefulness (often EEG-defined; seconds) | Prolonged SD protocols | Inevitable with accumulating sleep debt ([Colavito et al., 2013](https://doi.org/10.3389/fnsys.2013.00106) citing Friedman et al.) |
| **Video-defined sleep** (immobility proxy) | Continuous inactivity **≥ ~40 s** (often ≥95% body area stationary) | Home-cage video sleep phenotyping | Correlates with EEG sleep; **short pauses are excluded** ([Pack et al., 2007](https://doi.org/10.1152/physiolgenomics.00139.2006); [Fisher et al., 2012](https://doi.org/10.1177/0748730411431550); COMPASS PIR variant [Brown et al., 2017](https://doi.org/10.12688/wellcomeopenres.9892.2)) |
| **Quiet wakefulness** | Awake but not locomoting / not exploring; can bias immobility→sleep proxies | Home-cage physiology; sleep scoring caveats | Distinct from sleep; short quiet bouts can inflate or fragment immobility-based sleep estimates |

**Rule of thumb for this repo:** do **not** equate cluster 13 with classical **fear freezing** unless bout context (threat cues, posture, duration, autonomic correlates) supports it. Prefer **pause / standstill / low-velocity syllable** language until function is tested. Do **not** equate cluster 13 with **SD sleep** unless bout length and context clear the Pack/Fisher ≥40 s video-sleep bar (and preferably EEG).

---

## Relevant studies (hits)

| Name they used | Paradigm | Video / measure | Ethological claim (as stated) | DOI / link |
|----------------|----------|-----------------|-------------------------------|------------|
| **Pausing** vs **freezing** | Open field; wild-derived + lab strains; 12-item ethogram | Live observation in 5 s bins + video tracking for transitions; 10 min | Pausing = brief inactivity (&lt;3 s); freezing = longer stationary (&gt;3 s); both novelty/anxiety-related ethogram items | [Takahashi et al., 2006](https://doi.org/10.1007/s10519-005-9038-3); defs in [MPD Koide3](https://phenome.jax.org/projects/Koide3) |
| **Pause** module / syllable | Open field; genetics, TMT predator odor | Depth video → AR-HMM MoSeq | Sub-second modules include “pause”; freezing modules appear under TMT (distinct from baseline pauses); Ror1β mutants upregulate brief pause/headbob modules | [Wiltschko et al., 2015](https://doi.org/10.1016/j.neuron.2015.11.031) |
| **Pauses** among syllables | Open field; pharmacobehavioral space | Depth MoSeq | Syllables include “darts, rears, pauses, turns”; long-term pausing under high-dose haloperidol (catalepsy-like); CNTNAP2 phenotype includes downregulated pauses | [Wiltschko et al., 2020](https://doi.org/10.1038/s41593-020-00706-3) |
| **Pauses** as example syllables | Methods / kpMS | Keypoints → keypoint-MoSeq | MoSeq motifs exemplified as “rears, turns and pauses”; still periods highlight keypoint jitter vs true stillness | [Weinreb et al., 2024](https://doi.org/10.1038/s41592-024-02318-2) |
| **Pause** (human ground truth) | Open-field pose videos; method comparison | DLC/SLEAP pose → B-SOiD, VAME, BFA, kpMS | Expert labels include **pause** alongside walk, rear, groom, “stand and sniff” | [Mlost et al., 2025](https://doi.org/10.1016/j.patter.2025.101237) |
| **Quiescence** (coarse class) | Open field | DLC → B-SOiD unsupervised clusters | Clusters mapped onto ethogram buckets including quiescence | [Hsu & Yttri, 2021](https://doi.org/10.1038/s41467-021-25420-x) |
| **Standstill** (+ local exploration) | Rat open field; RGB-D | Kinect depth/RGB; manual ethogram; SVM | Standstill vs local/moving exploration/walking/rearing/grooming; Standstill+ merges standstill + local exploration | [Gerós et al., 2020](https://doi.org/10.3758/s13428-020-01381-9) |
| **Freezing** (contrast class) | Fear conditioning, OF, EPM, novel object exploration | DLC keypoints → BehaviorDEPOT velocity heuristics | Freezing = no movement except respiration; **not** the same as generic immobility | [Gabriel et al., 2022](https://doi.org/10.7554/elife.74314) |
| **Pause-and-play motor arrest**; natural **arrest bouts** | Corridor / cylinder / OF; optogenetics | Side/bottom video + EMG + respiration/ECG | Chx10-PPN arrest holds locomotion mid-cycle then resumes; distinct from vlPAG freezing; natural OF arrests 500 ms–2 s with similar autonomic signature; proposed preparatory/arousal response to salient cues | [Goñi-Erro et al., 2023](https://doi.org/10.1038/s41593-023-01396-3) |
| **Pausing** during intermittent locomotion | Travel between food sites (squirrels/chipmunks) | Videotape of locomotion | Brief pauses can improve antipredator vigilance; not prey-search in that assay | [McAdam & Kramer, 1998](https://doi.org/10.1006/anbe.1997.0592) |
| **Intermittent locomotion** (review) | Cross-taxa locomotion ecology | Synthesis | Pauses are common; proposed benefits: perception, predator/prey detection, endurance | [Kramer & McLaughlin, 2001](https://doi.org/10.1093/icb/41.2.137) |
| **Inactivity forms** (review) | Welfare / affective ethology | Conceptual + literature | Freezing ≠ rest ≠ tonic immobility; inactivity is heterogeneous | [Fureix & Meagher, 2015](https://doi.org/10.1016/j.applanim.2015.08.036) |
| **Immobility / stops** (scalar) | Developmental OFT (rats) | Overhead video + centroid analysis | Reports time immobile, number of stops — coarse, not ethogram-typed pause | e.g. automated OF gait systems; not a strong ethological analogue |
| NOR **exploration** (near-miss) | NOR / NORT | DLC + classifiers; nose-to-object zones | Scores investigation/attention, **not** a dedicated “hesitation pause” syllable | e.g. [Ishii et al., 2024](https://doi.org/10.1016/j.bbr.2024.115278); commercial multipoint NOR tracking |
| **Microsleep** (SD neighbor) | Prolonged total / platform / handling SD | Usually EEG (+ behavior); methods reviews | Short sleep intrusions under sleep debt — sleep intrusion, not ethogram pausing | [Colavito et al., 2013](https://doi.org/10.3389/fnsys.2013.00106) |
| **≥40 s immobility = sleep** (SD / sleep phenotyping) | Home cage; baseline + drugs; circadian screens | Video tracking (Pack/Fisher) or PIR (COMPASS) | Extended immobility predicts EEG sleep; **opposite duration band** from brief pause | [Pack et al., 2007](https://doi.org/10.1152/physiolgenomics.00139.2006); [Fisher et al., 2012](https://doi.org/10.1177/0748730411431550) |
| **OFT / FST immobility after SD** (near-miss) | REM / total SD → open field, EPM, FST/TST | Overhead video; coarse scalars | Distance, center time, total immobility / despair-like floating — direction varies by protocol/sex | e.g. [Gonzalez-Castañeda et al., 2016](https://doi.org/10.1538/expanim.15-0054); many OFT-after-SD papers |

---

## Sleep deprivation (SD) pass

**Question for this section:** Does the brief non-fear pause motif have a documented association in rodent SD studies (especially video-based)?

### Verdict

**No strong direct association as a named ethological motif.** SD literature talks about inactivity a lot, but almost never as Takahashi/MoSeq/Gerós-style brief pauses interrupting exploration. Association is **indirect**: sleep pressure increases quiet/immobile time and can produce microsleeps; those are neighboring constructs, not the same claim.

### Constructs SD papers actually use

| Construct | Timescale / definition | Link to SD | Match to brief exploratory pause? |
|-----------|------------------------|------------|-----------------------------------|
| **Microsleep** | seconds; sleep into wake (often EEG) | Accumulates with prolonged SD | Partial neighbor — sleep intrusion, not ethogram pausing |
| **Video sleep proxy** | continuous immobility **≥ ~40 s** | Validated vs EEG as sleep | **Opposite** band — short pauses are *excluded* so they are not scored as sleep |
| **Quiet wake** | awake, low/no locomotion | Can confound immobility→sleep scoring | Related state family; not OF “pause” ethology |
| **OFT / anxiety endpoints after SD** | distance, center time, coarse immobility | Common; hyper- vs hypoactivity depends on protocol/sex | Too coarse — not pause vs freeze vs rest |
| **FST/TST immobility** | floating / hanging still | Often read as depression-like after SD | Different assay meaning |

### What was *not* found

No primary SD study found that treats as a standard SD ethogram endpoint:

- Takahashi/Koide **pausing** (&lt;3 s)
- MoSeq / kpMS **pause syllables**
- Gerós **standstill**
- Goñi-Erro **pause-and-play motor arrest**

MoSeq/kpMS tooling *could* quantify pause-syllable usage after SD, but that is method availability — not an established SD ethology claim in the literature searched (2026-08-27).

### Implication for this repo (`noSD` / NOR)

If cluster 13 rises under SD, literature does **not** hand a ready “cluster 13 = known SD pause” citation. Closest conceptual neighbors:

1. **Microsleep** — only if duration/context look like sleep intrusion (ideally EEG).
2. **Fatigue / quieting** — coarse OFT hypoactivity after some SD protocols (inconsistent).
3. **Not video-defined sleep** — Pack/Fisher ≥40 s is the clean SD-adjacent duration cut; brief exploratory pauses sit **below** that bar by design.

**Local litmus:** compare cluster-13 bout-length distributions to **&lt;40 s** (not Pack/Fisher sleep) vs **≥40 s** (sleep-proxy territory), alongside the ethology cuts already noted (&lt;3 s Takahashi; 0.5–2 s Goñi-Erro).

---

## Closest analogues to cluster 13 (ranked)

1. **MoSeq / keypoint-MoSeq “pause” syllables** — Same methodological family (unsupervised pose motifs). Wiltschko et al. treat pause as a first-class syllable label; Weinreb et al. list pauses with rears/turns. **Mismatch:** classic MoSeq pauses are typically **sub-second**; cluster 13 is described as **long** bouts — may be a sticky/long-duration still-like state or a duration-band merge, not a textbook MoSeq pause.
2. **Takahashi/Koide ethogram “pausing”** — Explicit non-fear brief inactivity, duration-split from freezing. **Mismatch:** scored by human 5 s presence/absence, not kpMS kinematics; “crooked” posture not part of the definition.
3. **Goñi-Erro et al. natural motor arrest (0.5–2 s)** — Strongest **non-fear functional** circuit story (pause-and-play vs freeze). **Mismatch:** defined by global motor hold + autonomic co-signature; cluster 13 is kinematic clustering without autonomic validation; “crooked” may or may not match mid-cycle holds.
4. **Gerós “standstill” / “Standstill+”** — Clean video ethogram neighbor (still vs local sniffing exploration). **Mismatch:** supervised coarse classes; local exploration may absorb what look like “crooked still” sniffing bouts.
5. **Mlost et al. human label “pause”** — Shows modern pose labs still use “pause” as an annotation class when validating unsupervised tools. **Mismatch:** evaluation paper, not ethology of NOR.
6. **McAdam & Kramer intermittent pauses** — Best **ecological function** language (vigilance). **Mismatch:** sciurid travel, not mouse NOR; not pose syllables.
7. **SD microsleep / quieting (weak)** — Only as a *hypothesis family* under sleep debt, not as a scored ethogram match. **Mismatch:** microsleeps are sleep intrusions; Pack/Fisher sleep is ≥40 s; OFT-after-SD reports coarse locomotion/anxiety, not pause syllables.

**Gaps / mismatches to state clearly**

- No primary NOR paper found that treats **kpMS pause syllables** (or “hesitation micro-pauses”) as a standard cognitive endpoint.
- **Freezing literature is a false friend** for cluster 13 unless threat context is shown.
- **SD literature is also a false friend** for cluster 13 unless bout length/context support microsleep or ≥40 s sleep-proxy stillness — and even then, that is sleep/fatigue, not ethogram pausing.
- **“Long, slow, crooked”** is richer than pure standstill; may blend pause with slow turning, stretch-attend, or local investigation — literature rarely packages those into one named motif.
- Scalar **immobility / number of stops** from centroid trackers collapses ethologically distinct states ([Fureix & Meagher, 2015](https://doi.org/10.1016/j.applanim.2015.08.036)).

---

## Relevance back to NOR / kpMS ethology

For OpenEthoMaze NOR_TX work:

1. **Label carefully.** Prefer **pause / still-like syllable** or ethogram **pausing**, not **freezing**, unless crowd movies + context match defensive freeze criteria ([Gabriel et al., 2022](https://doi.org/10.7554/elife.74314)).
2. **Expect method homology, not claim homology.** MoSeq papers justify calling a low-velocity motif a **pause**; they do **not** by themselves justify “hesitation about the novel object.”
3. **Test function with local design.** Candidate ethological hypotheses (with different predictions):
   - **Appraisal / object-related pause** — enrichment near objects / novelty step (NOR-specific).
   - **Preparatory motor arrest** — mid-locomotion holds like Goñi-Erro natural arrests (cue-salience, not necessarily fear).
   - **Vigilance / intermittent locomotion** — more pauses when risk or uncertainty is high (ecology analogy).
   - **Non-specific hypoactivity / sedative-like stillness** — pharmaco MoSeq “long-term pausing” pattern ([Wiltschko et al., 2020](https://doi.org/10.1038/s41593-020-00706-3)).
   - **Sleep-pressure quieting / microsleep** — enrichment under SD vs `noSD`, especially if bouts lengthen toward Pack/Fisher territory or crowd movies look sleep-like rather than mid-exploration halt (**provisional**; not a named SD ethogram claim).
4. **Disambiguate standstill vs local exploration.** Gerós-style split matters: still body with active sniffing is often **local exploration**, not pure pause.
5. **Duration is diagnostic.** Useful benchmarks against cluster 13 bout-length distributions:
   - Takahashi **&lt;3 s** vs **&gt;3 s** (pausing vs freezing ethogram cut)
   - Goñi-Erro **0.5–2 s** natural motor arrests
   - Pack/Fisher **≥40 s** continuous immobility (video sleep proxy — *not* brief pause)

**Bottom line for ethology write-ups:** cite MoSeq pause syllables + Koide pausing for **what it looks like**; cite Goñi-Erro / Kramer for **what it might mean**; cite Pack/Fisher + microsleep reviews only to **bound** sleep-pressure alternatives (duration/context), not as synonymy; keep NOR and SD functional claims **provisional** until object-aligned bout analyses (already in `scratch/nor_object_mi/`) are tied to crowd-movie QC and bout-length cuts.

---

## Sources

1. Takahashi A, Kato K, Makino J, Shiroishi T, Koide T. Multivariate analysis of temporal descriptions of open-field behavior in wild-derived mouse strains. *Behav Genet*. 2006. https://doi.org/10.1007/s10519-005-9038-3 — operational defs archived in Mouse Phenome Database [Koide3](https://phenome.jax.org/projects/Koide3).
2. Wiltschko AB et al. Mapping sub-second structure in mouse behavior. *Neuron*. 2015. https://doi.org/10.1016/j.neuron.2015.11.031
3. Wiltschko AB et al. Revealing the structure of pharmacobehavioral space through Motion Sequencing. *Nat Neurosci*. 2020. https://doi.org/10.1038/s41593-020-00706-3
4. Weinreb C et al. Keypoint-MoSeq: parsing behavior by linking point tracking to pose dynamics. *Nat Methods*. 2024. https://doi.org/10.1038/s41592-024-02318-2
5. Hsu AI, Yttri EA. B-SOiD, an open-source unsupervised algorithm for identification and fast prediction of behaviors. *Nat Commun*. 2021. https://doi.org/10.1038/s41467-021-25420-x
6. Mlost J et al. Evaluation of unsupervised learning algorithms for the classification of behavior from pose estimation data. *Patterns*. 2025. https://doi.org/10.1016/j.patter.2025.101237
7. Gerós A, Magalhães A, Aguiar P. Improved 3D tracking and automated classification of rodents’ behavioral activity using depth-sensing cameras. *Behav Res Methods*. 2020. https://doi.org/10.3758/s13428-020-01381-9
8. Gabriel CJ et al. BehaviorDEPOT is a simple, flexible tool for automated behavioral detection based on markerless pose tracking. *eLife*. 2022. https://doi.org/10.7554/elife.74314
9. Goñi-Erro H, Selvan R, Caggiano V, Leiras R, Kiehn O. Pedunculopontine Chx10+ neurons control global motor arrest in mice. *Nat Neurosci*. 2023. https://doi.org/10.1038/s41593-023-01396-3
10. McAdam AG, Kramer DL. Vigilance as a benefit of intermittent locomotion in small mammals. *Anim Behav*. 1998. https://doi.org/10.1006/anbe.1997.0592
11. Kramer DL, McLaughlin RL. The behavioral ecology of intermittent locomotion. *Am Zool / Integr Comp Biol*. 2001. https://doi.org/10.1093/icb/41.2.137
12. Fureix C, Meagher RK. What can inactivity (in its various forms) reveal about affective states in non-human animals? A review. *Appl Anim Behav Sci*. 2015. https://doi.org/10.1016/j.applanim.2015.08.036
13. Fanselow MS, Bolles RC. Naloxone and shock-elicited freezing in the rat. *J Comp Physiol Psychol*. 1979. https://doi.org/10.1037/h0077609 (freezing definition lineage used by later automated tools).
14. Ishii et al. Automated analysis of a novel object recognition test in mice using image processing and machine learning. *Behav Brain Res*. 2024. https://doi.org/10.1016/j.bbr.2024.115278 (NOR video automation near-miss: exploration, not pause ethogram).
15. Pack AI et al. Novel method for high-throughput phenotyping of sleep in mice. *Physiol Genomics*. 2007. https://doi.org/10.1152/physiolgenomics.00139.2006 (≥40 s continuous inactivity as video sleep proxy).
16. Fisher SP et al. Rapid assessment of sleep-wake behavior in mice. *J Biol Rhythms*. 2012. https://doi.org/10.1177/0748730411431550 (video immobility sleep scoring; 95% area stationary refinement).
17. Brown LA, Hasan S, Foster RG, Peirson SN. COMPASS: Continuous Open Mouse Phenotyping of Activity and Sleep Status. *Wellcome Open Res*. 2017. https://doi.org/10.12688/wellcomeopenres.9892.2 (PIR &gt;40 s immobility ≈ EEG sleep; notes quiet-wake caveats).
18. Colavito V et al. Experimental sleep deprivation as a tool to test memory deficits in rodents. *Front Syst Neurosci*. 2013. https://doi.org/10.3389/fnsys.2013.00106 (methods review; microsleeps under accumulating sleep debt).
19. Gonzalez-Castañeda RE et al. Sex-related effects of sleep deprivation on depressive- and anxiety-like behaviors in mice. *Exp Anim*. 2016. https://doi.org/10.1538/expanim.15-0054 (example OFT/FST-after-PSD: coarse locomotion/immobility, not pause ethogram).

**Not used as primary authority:** commercial blog ethograms / ANY-maze FAQ (useful for software definitions only); Stack Exchange summaries of intermittent locomotion; commercial “resting & immobility” product pages.
