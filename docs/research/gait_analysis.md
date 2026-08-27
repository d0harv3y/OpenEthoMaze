# Gait Analysis — Research Notes

**Question:** What is gait analysis?

**Sources:** Primary literature, society consensus statements, clinical practice guidelines, and peer-reviewed protocols (not blog summaries). Compiled 2026-07-09.

---

## Summary

Gait analysis is the **quantitative study of locomotion**, most commonly walking, by measuring how the body and limbs move over time and (when available) the forces and muscle activity that produce that motion. In clinical medicine it means **instrumented measurement plus interpretation** to support diagnosis, treatment planning, or monitoring of gait disorders ([Baker, 2006](https://doi.org/10.1186/1743-0003-3-4); [Benedetti et al., 2017](https://doi.org/10.1016/j.gaitpost.2017.08.003)). Outputs are grouped into **kinematic** (motion), **kinetic** (forces/moments), and **spatiotemporal** (timing and placement) parameters, often organized around the **gait cycle** from one foot contact to the next ([Perry & Burnfield, 2010](https://doi.org/10.1201/9781003525592-2)).

Methods range from **visual observation** through **3D motion capture, force plates, EMG, and wearables** in humans, to **footprint imaging and high-speed videography** in animals. Applications span rehabilitation, neurology, orthopedics, sports, veterinary lameness assessment, forensic identification, and legged robotics. In **rodent neuroscience**, automated gait systems (CatWalk, DigiGait, MouseWalker, GAITOR) provide sensitive motor endpoints for CNS/PNS disease models ([Garrick et al., 2021](https://doi.org/10.1002/cpz1.220); [Mendes et al., 2015](https://doi.org/10.1186/s12915-015-0154-0)).

For **ethology / OpenEthoMaze-style work**, classical gait analysis is a **limb-cycle, footfall-centric** motor assay, whereas syllable ethograms from pose (e.g. kpMS) capture **whole-body behavioral motifs** at bout scale; the two overlap on locomotion speed and coordination but differ in grain, apparatus, and interpretive frame.

---

## Definition

### Core concept

| Source | Definition |
|--------|------------|
| **NCBI StatPearls** (forensic context) | "Gait analysis refers to the **systematic study of human movement during walking**." ([NCBI Bookshelf NBK557684](https://www.ncbi.nlm.nih.gov/books/NBK557684/)) |
| **Richard Baker** (rehabilitation review) | "Gait analysis will be assumed to refer to the **instrumented measurement of the movement patterns that make up walking** and the associated interpretation of these." Core measurements: joint kinematics and kinetics; often supplemented by EMG, oxygen consumption, and foot pressures ([Baker, 2006](https://doi.org/10.1186/1743-0003-3-4)). |
| **SIAMOC consensus** (Italian Society of Clinical Movement Analysis) | "**Gait Analysis is a process of instrumented measurement and evaluation of walking ability** in patients with impairments specific to locomotion." GA aims to answer clinical questions and support medical decision-making; the term **Clinical Gait Analysis (CGA)** is used when measurements are tied to an individual clinical problem ([Benedetti et al., 2017](https://doi.org/10.1016/j.gaitpost.2017.08.003)). |
| **Custos et al.** (clinical facts review) | "**Clinical gait analysis is the process of recording and interpreting biomechanical measurements of walking** in order to support clinical decision-making in case of gait dysfunction." ([Custos et al., 2016](http://www.analisedemarcha.com/papers/custos/2016_Gait%20analysis%20technology%20and%20clinical%20applications%20-%20Edizione%20Minerva%20Medica.pdf)) |
| **Veterinary (canine CV review)** | "Gait analysis is a sub-field in bio-mechanics which refers to the **systematic study of animal and human locomotion** by measuring body movements, mechanics, and the activity of the muscles." ([Frontiers in Veterinary Science, 2026](https://doi.org/10.3389/fvets.2026.1729697)) |
| **Wearable-sensor systematic review** | "Gait analysis (GA), which **systematically examines human movement**, is crucial in several fields, including sports, clinical diagnoses, physical ergonomics, and rehabilitation." ([Prisco et al., 2024](https://doi.org/10.3390/diagnostics15010036)) |

### Gait vs. gait analysis

- **Gait** is the manner of walking or locomotion; **gait analysis** is the measurement and (often) clinical or scientific interpretation of that locomotion.
- **Observational gait analysis** uses visual assessment without specialized instrumentation ([AAPC clinical review citing Sutherland, 2001/2005](https://www.aapc.com/codes/webroot/upload/general_pages_docs/document/Gait_Analysis.pdf)).
- **Instrumented / quantitative / clinical gait analysis** uses technology (motion capture, force platforms, EMG, pressure mats, IMUs, ventral-plane videography) to produce objective parameters ([GAMMA, 2024](https://doi.org/10.1016/j.gaitpost.2024.11.018); [Garrick et al., 2021](https://doi.org/10.1002/cpz1.220)).

### Gait cycle (organizing unit)

Perry and Burnfield define the **gait cycle (GC)** as the repetitive limb-motion sequence used to move the body forward while maintaining stance stability. Each cycle is divided into:

- **Stance phase** (~60% of cycle): foot on ground, from initial contact (IC) through toe-off.
- **Swing phase** (~40%): foot in air for limb advancement.

Perry further subdivides the cycle into **eight functional phases** (initial contact, loading response, midstance, terminal stance, pre-swing, initial swing, midswing, terminal swing) ([Perry & Burnfield, 2010](https://doi.org/10.1201/9781003525592-2); [AAPMR KnowledgeNow](https://now.aapmr.org/biomechanics-normal-gait/)).

---

## What is measured

Gait analysis typically reports three families of parameters. The International Society of Biomechanics (ISB) publishes reporting standards for **joint kinematics** (Wu et al., 2002/2005) and **intersegmental forces and moments** ([ISB, 2020](https://doi.org/10.1016/j.jbiomech.2019.10.029); [isbweb.org standards](https://isbweb.org/members/29-standards-documents)).

### 1. Kinematic parameters (motion)

Describe **positions, orientations, and velocities** of body segments and joints without direct force measurement.

| Examples | Notes |
|----------|-------|
| Joint angles (hip, knee, ankle, pelvis, trunk) | 3D segmental models; ISB Joint Coordinate System recommended for reporting ([ISB standards](https://isbweb.org/members/29-standards-documents)) |
| Segment orientations / trajectories | Marker-based or markerless pose estimation |
| Foot / paw placement | Especially in animal ventral-plane imaging |
| Range of motion, symmetry between limbs | Clinical and veterinary lameness indices |

Clinical 3D-IGA for cerebral palsy explicitly provides **kinematics (joint angles)**, **kinetics (joint moments/powers)**, and **muscle activity** ([CP clinical practice guideline, 2024](https://pubmed.ncbi.nlm.nih.gov/38568266/)).

### 2. Kinetic parameters (forces and moments)

Describe **interaction with the environment** and internal joint loading.

| Examples | Measurement |
|----------|-------------|
| Ground reaction forces (GRF) | Force platforms, pressure walkways |
| Joint moments and powers | Inverse dynamics from kinematics + GRF + anthropometry |
| Peak vertical force, impulse, symmetry indices | Common in veterinary kinetic gait analysis ([Keegan et al., 2022 review](https://doi.org/10.1016/j.jevs.2022.03.009)) |
| Center of pressure (COP) trajectories | Pressure mats / walkways |
| Foot pressures | In-shoe or platform sensors |

ISB notes that intersegmental forces and moments represent **net loads at a joint** and require explicit reporting of coordinate systems, normalization, and perspective ([ISB kinetics recommendations](https://isbweb.org/news/isb-now/175-isb-now-march-2020/711-isb-recommendations-reporting-of-intersegmental-forces-and-moments)).

### 3. Spatiotemporal (ST) parameters

Describe **when and where** the feet (or paws) contact the ground and how the body progresses.

| Parameter | Typical meaning |
|-----------|-----------------|
| Gait speed, cadence | Progression rate |
| Step length, stride length, step width | Spatial placement |
| Stance / swing duration | Phase timing (% of cycle) |
| Double-support time | Both feet on ground (bipedal) |
| Stride time, cycle duration | Temporal rhythm |
| Symmetry / variability | Left–right comparison, stride-to-stride consistency ([Gouelle & Mégrot, 2016](https://doi.org/10.1007/978-3-319-30808-1_35-1)) |

Rodent systems additionally report **paw area, inter-limb coordination, print position**, and **swing/stance speed** ([Garrick et al., 2021](https://doi.org/10.1002/cpz1.220); [DigiGait product documentation](https://mousespecifics.com/digigait/)).

### Ancillary measures

- **Surface EMG**: muscle activation timing and amplitude ([Sutherland, 2001](https://doi.org/10.1016/s0966-6362(01)00141-4); Hermens et al. SEMG sensor placement standards cited in SIAMOC).
- **Metabolic cost**: oxygen consumption during walking (Perry framework; clinical CP assessments).
- **Muscle–tendon function**: emerging imaging and modeling ([Baker, 2006](https://doi.org/10.1186/1743-0003-3-4)).

---

## Methods and modalities

### Human — clinical

| Modality | Role | Primary sources |
|----------|------|-----------------|
| **Visual / observational** | Screening; limited precision | [AAPC gait analysis review](https://www.aapc.com/codes/webroot/upload/general_pages_docs/document/Gait_Analysis.pdf) |
| **3D optical motion capture** | Gold standard for joint kinematics in CGA labs | [Baker, 2006](https://doi.org/10.1186/1743-0003-3-4); [GAMMA, 2024](https://doi.org/10.1016/j.gaitpost.2024.11.018) |
| **Force platforms / walkways** | GRF, COP, symmetry | [ISB kinetics reporting](https://doi.org/10.1016/j.jbiomech.2019.10.029) |
| **EMG** | Muscle timing | SIAMOC consensus; Sutherland evolution papers |
| **Wearable IMUs** | Portable ST and joint kinematics; validation vs. optical capture ongoing | [Prisco et al., 2024](https://doi.org/10.3390/diagnostics15010036) |
| **Treadmill vs. overground** | Standardized speed vs. ecological walking; lab setup choices in GAMMA recommendations | [GAMMA, 2024](https://doi.org/10.1016/j.gaitpost.2024.11.018) |

Clinical gait analysis is **not** generic parameter logging: SIAMOC stresses that measurements must be **linked to a specific clinical question** and interpreted in that context ([Benedetti et al., 2017](https://doi.org/10.1016/j.gaitpost.2017.08.003)).

### Human — research

Research gait analysis shares instrumentation with CGA but often targets **population inference**, biomechanical theory, or algorithm validation rather than individual treatment decisions ([Baker, 2006](https://doi.org/10.1186/1743-0003-3-4)). Sports biomechanics, ergonomics, and wearable validation studies fall here ([Prisco et al., 2024](https://doi.org/10.3390/diagnostics15010036)).

### Animal / locomotion research

| Modality | Species | Notes |
|----------|---------|-------|
| **Ink / static footprints** | Rodents | Early method; limited dynamic parameters ([Vandeputte et al., 2023 review](https://doi.org/10.3389/fnbeh.2023.1147784)) |
| **fTIR footprint imaging** (CatWalk XT, MouseWalker) | Rodents | High-resolution paw contact without body markers ([Mendes et al., 2015](https://doi.org/10.1186/s12915-015-0154-0); [Garrick et al., 2021](https://doi.org/10.1002/cpz1.220)) |
| **Ventral-plane videography** (DigiGait) | Mice, rats | Treadmill or voluntary corridor; 50+ indices per limb ([DigiGait](https://mousespecifics.com/digigait/); [Kipp et al., 2025](https://doi.org/10.3390/cells14130969)) |
| **Open-source suites** (GAITOR, etc.) | Rodents | Customizable hardware/software for injury models ([Jacobs et al., 2018](https://doi.org/10.1038/s41598-018-28134-1)) |
| **Force plates / pressure walkways** | Dogs, horses | Kinetic lameness assessment; symmetry indices ([Keegan et al., 2022](https://doi.org/10.1016/j.jevs.2022.03.009); [JAVMA equine tutorial, 2026](https://doi.org/10.2460/javma.25.12.0784)) |
| **IMUs / camera-based systems** | Horses, dogs | Clinical objective lameness tools ([JAVMA, 2026](https://doi.org/10.2460/javma.25.12.0784)) |

**Walkway vs. treadmill:** Non-moving walkways (CatWalk) favor **natural self-selected speed**; treadmills (DigiGait) enable **many strides at controlled speed** ([Garrick et al., 2021](https://doi.org/10.1002/cpz1.220)).

### Robotics

In legged robotics, "gait" often means a **locomotion controller pattern** (phase timing, foot placement, joint trajectories). Gait analysis here means **quantitative comparison** of robot locomotion to biological reference—kinematic/kinetic divergence, energy distribution, symmetry—e.g. the Gait Divergence Analysis Framework comparing human and humanoid walking ([arXiv:2602.21666](https://doi.org/10.48550/arxiv.2602.21666)). Machine-learning gait phase classification from IMUs/encoders supports exoskeleton and orthosis control ([Kolaghassi et al., 2021](https://doi.org/10.1109/ACCESS.2021.3104464)).

---

## Applications

### Medicine and rehabilitation

| Application | How gait analysis is used | Source |
|-------------|---------------------------|--------|
| **Cerebral palsy** | Surgical / orthotic / therapy decisions; 3D-IGA evidence-based guideline | [CP CPG, 2024](https://pubmed.ncbi.nlm.nih.gov/38568266/) |
| **Stroke, spinal cord injury, upper motor neuron disorders** | Assess severity, plan intervention, monitor progress | [Custos et al., 2016](http://www.analisedemarcha.com/papers/custos/2016_Gait%20analysis%20technology%20and%20clinical%20applications%20-%20Edizione%20Minerva%20Medica.pdf); [Patrick, 2003](https://doi.org/10.1038/sj.sc.3101524) |
| **Lower-limb amputation / prosthetics** | Socket fit, alignment, gait retraining | SIAMOC appropriateness statements |
| **Fall risk / elderly mobility** | ST variability, speed, symmetry | [Prisco et al., 2024](https://doi.org/10.3390/diagnostics15010036) |
| **Parkinson's and movement disorders** | Characteristic gait signatures (e.g. shuffling) | [Garrick et al., 2021](https://doi.org/10.1002/cpz1.220) (rodent models); clinical CGA literature in SIAMOC |

Brand's framework (via Baker): clinical tests serve **diagnosis, assessment, monitoring, and outcome prediction** ([Baker, 2006](https://doi.org/10.1186/1743-0003-3-4)).

### Neuroscience (human)

Instrumented gait analysis quantifies motor deficits from **CNS and PNS pathology**, supports rehabilitation engineering, and complements cognitive assays that assume intact locomotion ([Baker, 2006](https://doi.org/10.1186/1743-0003-3-4)).

### Veterinary medicine

Objective gait analysis detects **lameness** (pathological alteration of normal gait), monitors **musculoskeletal and neurological conditions**, and evaluates treatment response in dogs and horses ([Keegan et al., 2022](https://doi.org/10.1016/j.jevs.2022.03.009); [van Weeren et al., 2017 definition of lameness](https://doi.org/10.1016/j.jevs.2017.12.006) cited in induced-lameness review). Kinetic force-plate analysis is widely validated; camera and IMU systems are entering routine practice ([JAVMA, 2026](https://doi.org/10.2460/javma.25.12.0784)).

### Sports and ergonomics

Gait analysis supports **performance optimization, injury prevention, and training design** ([Prisco et al., 2024](https://doi.org/10.3390/diagnostics15010036)).

### Forensics

Forensic gait analysis compares suspect gait to crime-scene footprints or CCTV; it is a **supportive** identification method, not standalone, because unique gait identification is not fully validated ([NCBI NBK557684](https://www.ncbi.nlm.nih.gov/books/NBK557684/)).

### Robotics and prosthetics

Biological gait analysis informs **humanoid controllers, exoskeletons, and prosthetic design**; robotic gait analysis evaluates how closely machines reproduce human kinematics/kinetics ([Mikolajczyk et al., 2022](https://doi.org/10.3390/s22124440); [Kolaghassi et al., 2021](https://doi.org/10.1109/ACCESS.2021.3104464)).

---

## Gait analysis in animal/rodent research (ethology & neuroscience)

### Why rodents?

Rodents are standard models for **toxicology, drug development, transgenic phenotyping, and CNS/PNS injury/disease**. Motor function is a critical behavioral endpoint; gait deficits can confound cognitive assays that depend on mobility ([Garrick et al., 2021](https://doi.org/10.1002/cpz1.220)). Rodents may **mask pain/disability** and compensate quadrupedally, so sensitive automated gait measures are valued over eyeball scoring alone ([Garrick et al., 2021](https://doi.org/10.1002/cpz1.220); Saunders et al., 2017 cited therein).

### Common assays vs. gait analysis

| Assay | What it measures | Relation to gait analysis |
|-------|------------------|---------------------------|
| **Open field** | Arena locomotion, exploration, anxiety-related movement | Gross locomotion; not footfall-resolved ([Coughlin protocol, 2024](https://doi.org/10.17504/protocols.io.6qpvr8jbzlmk/v2)) |
| **Rotarod** | Balance/coordination; latency to fall | Complementary motor test; not stride kinematics |
| **Beam / wire hang** | Skilled locomotion / strength | Complementary |
| **Automated gait analysis** | Stride, stance/swing, paw metrics, coordination | **Limb-cycle–resolved** motor phenotype |

A typical motor battery combines several assays; gait analysis provides **multidimensional limb-level detail** ([Coughlin protocol, 2024](https://doi.org/10.17504/protocols.io.6qpvr8jbzlmk/v2)).

### Disease models using rodent gait

CatWalk XT and related systems are widely used in models of **sciatic nerve injury, spinal cord injury, TBI, MS, Parkinson's, Huntington's, stroke**, and peripheral neuropathy ([Vandeputte et al., 2023](https://doi.org/10.3389/fnbeh.2023.1147784); [Jacobs et al., 2018](https://doi.org/10.1038/s41598-018-28134-1)). GAITOR demonstrated model-specific compensatory patterns in joint pain, nerve injury, contracture, and SCI ([Jacobs et al., 2018](https://doi.org/10.1038/s41598-018-28134-1)).

### Relation to ethology and pose-based syllables (OpenEthoMaze context)

OpenEthoMaze's ethogram track ([`docs/ethogram_scope.md`](../ethogram_scope.md)) targets **discrete behavioral syllables** from pose (kpMS), with bout-level scalars (centroid, heading, speed, blob area) ([`docs/bout_feature_contract.md`](../bout_feature_contract.md)). This is **ethological state segmentation**, not classical instrumented gait analysis:

| Dimension | Classical rodent gait analysis | OpenEthoMaze / kpMS ethogram |
|-----------|-------------------------------|------------------------------|
| **Primary grain** | Footfall / limb cycle | Per-frame pose → syllable bout |
| **Apparatus** | Walkway, treadmill, force plate | Video + pose (arena, home cage, maze) |
| **Typical outputs** | Stance, swing, stride, paw area, coordination | Syllable ID, bout kinematics, grammar |
| **Question** | "Is locomotion impaired?" | "What behavior motifs occur, when, and how are they structured?" |

Overlap exists where syllables encode **locomotor motifs** (walk, turn, rear) and bout scalars capture **speed and heading**—kinematic quantities also used in gait studies—but ethograms do not by default report **limb-specific stance/swing or GRF**. Conversely, CatWalk/DigiGait do not label **grooming, rearing, or exploration bouts**. The approaches are **complementary motor/behavior endpoints** in rodent neuroscience.

Markerless pose estimation (DeepLabCut, SLEAP) is increasingly used to derive **kinematics from video** in both domains; rodent gait toolchains (GAITOR, MouseWalker, AutoGaitA) and ethology pipelines (kpMS, B-SOiD) represent different analysis layers on similar raw video ([Mendes et al., 2015](https://doi.org/10.1186/s12915-015-0154-0); OpenEthoMaze `docs/tracking_kpms_master_plan.md`).

---

## Key references

### Definitions and clinical practice

| Reference | DOI / URL |
|-----------|-----------|
| Baker R. Gait analysis methods in rehabilitation. *J NeuroEngineering Rehabil.* 2006. | https://doi.org/10.1186/1743-0003-3-4 |
| Benedetti MG et al. SIAMOC position paper on gait analysis in clinical practice. *Gait Posture.* 2017. | https://doi.org/10.1016/j.gaitpost.2017.08.003 |
| Custos RP et al. Gait analysis: clinical facts. *Minerva Medica.* 2016. | http://www.analisedemarcha.com/papers/custos/2016_Gait%20analysis%20technology%20and%20clinical%20applications%20-%20Edizione%20Minerva%20Medica.pdf |
| GAMMA association. Recommendations for standardization of clinical movement analysis laboratories. *Gait Posture.* 2024. | https://doi.org/10.1016/j.gaitpost.2024.11.018 |
| Three-Dimensional Instrumented Gait Analysis for Children With Cerebral Palsy: CPG. 2024. | https://pubmed.ncbi.nlm.nih.gov/38568266/ |
| Forensic Gait Analysis. *StatPearls.* NCBI Bookshelf. | https://www.ncbi.nlm.nih.gov/books/NBK557684/ |

### Gait cycle and spatiotemporal parameters

| Reference | DOI / URL |
|-----------|-----------|
| Perry J, Burnfield JM. *Gait Analysis: Normal and Pathological Function.* 2nd ed. 2010. | https://doi.org/10.1201/9781003525592-2 |
| Gouelle A, Mégrot F. Interpreting spatiotemporal parameters in clinical gait analysis. In: *Handbook of Human Motion.* 2016. | https://doi.org/10.1007/978-3-319-30808-1_35-1 |
| AAPMR KnowledgeNow: Biomechanics of Normal Gait. | https://now.aapmr.org/biomechanics-normal-gait/ |

### Biomechanics standards (ISB)

| Reference | DOI / URL |
|-----------|-----------|
| Wu G et al. ISB recommendation on definitions of joint coordinate systems. *J Biomech.* 2002/2005. | https://isbweb.org/members/29-standards-documents |
| Fregly BJ et al. ISB recommendations on reporting intersegmental forces and moments. *J Biomech.* 2020. | https://doi.org/10.1016/j.jbiomech.2019.10.029 |

### Wearables and methods

| Reference | DOI / URL |
|-----------|-----------|
| Prisco G et al. Validity of wearable inertial sensors for gait analysis: systematic review. *Diagnostics.* 2024. | https://doi.org/10.3390/diagnostics15010036 |

### Rodent gait / neuroscience

| Reference | DOI / URL |
|-----------|-----------|
| Garrick JM et al. Evaluating gait and locomotion in rodents with the CatWalk. *Curr Protoc.* 2021. | https://doi.org/10.1002/cpz1.220 |
| Mendes CS et al. Quantification of gait parameters in freely walking rodents (MouseWalker). *BMC Biol.* 2015. | https://doi.org/10.1186/s12915-015-0154-0 |
| Jacobs BY et al. The open source GAITOR Suite for rodent gait analysis. *Sci Rep.* 2018. | https://doi.org/10.1038/s41598-018-28134-1 |
| Vandeputte C et al. CatWalk XT gait parameters review across CNS/PNS models. *Front Behav Neurosci.* 2023. | https://doi.org/10.3389/fnbeh.2023.1147784 |
| Coughlin GM. Mouse motor behaviour protocol (open field, beam, hang, gait). *protocols.io* 2024. | https://doi.org/10.17504/protocols.io.6qpvr8jbzlmk/v2 |
| Kipp M et al. DigiGait in cuprizone demyelination model. *Cells.* 2025. | https://doi.org/10.3390/cells14130969 |

### Veterinary

| Reference | DOI / URL |
|-----------|-----------|
| Keegan KG et al. Kinetic symmetry indices and standing gait analysis in dogs. *J Equine Vet Sci.* 2022. | https://doi.org/10.1016/j.jevs.2022.03.009 |
| Keegan KG et al. Objective gait analysis in equine practice (JAVMA tutorial). 2026. | https://doi.org/10.2460/javma.25.12.0784 |
| Weeren PR van et al. Evidence for objective gait analysis (induced lameness review). *J Equine Vet Sci.* 2018. | https://doi.org/10.1016/j.jevs.2018.01.006 |
| Automatic gait analysis in canines using computer vision. *Front Vet Sci.* 2026. | https://doi.org/10.3389/fvets.2026.1729697 |

### Robotics

| Reference | DOI / URL |
|-----------|-----------|
| Mikolajczyk T et al. Recent advances in bipedal walking robots: gait, drive, sensors, control. *Sensors.* 2022. | https://doi.org/10.3390/s22124440 |
| Kolaghassi R et al. Intelligent algorithms in gait analysis for lower limb robotic systems. *IEEE Access.* 2021. | https://doi.org/10.1109/ACCESS.2021.3104464 |
| Biomechanical comparisons of human and humanoid gaits (GDAF). arXiv preprint. 2026. | https://doi.org/10.48550/arxiv.2602.21666 |

---

*Note: No `docs/research/` convention existed in OpenEthoMaze prior to this file; it is created here as the project's research-notes location.*
