# Rodent Frailty Index Features & Open-Field Kinematic Batteries — Research Notes

**Question:** What features belong in a full frailty index (FI) for laboratory mice and rodents, especially when scored from open-field (OF) or video/pose kinematics? What are the canonical FI constructions in the literature, which domains appear, does a published 8-item battery exist, what can top-view pose measure, and what 8-feature table is recommended for an open-field kinematic assay?

**Sources:** Primary literature from the labs that established rodent frailty indices (Rockwood, Howlett, Whitehead, Parks, Liu/Thompson, Kumar/Churchill), NIH/NIA gerontology frameworks, and computer vision pose literature (DeepLabCut, SuperAnimal). Compiled 2026-11-03.

---

## Implementation dictionary

Column definitions, movement hysteresis knobs, and EthoVision rearing vs
grooming notes for the current OEM feature table live in
[docs/data_dictionaries/INFO_of_frailty_metrics.md](../data_dictionaries/INFO_of_frailty_metrics.md).

## Read this first (for the PI ask)

If someone said “make a table with **8 features**” for open-field frailty, they almost certainly meant the published **Parks / Whitehead performance-based 8-item FI**:

1. total distance  
2. max distance between inactivity bouts  
3. movement duration  
4. percent time moving  
5. meander (deg/cm)  
6. average velocity  
7. rearing frequency  
8. **body weight** (scale — not from video)

That is the literature eight. Confirm with the PI before substituting.

Section 5 below is a **separate** proposal: an OEM **video-only** eight that drops weight and rearing in favor of thigmotaxis / elongation / speed IQR. Useful if the assay is pose-only and unlabeled; **not** identical to Parks/Whitehead. Do not report it as “the” 8-item FI without saying it was adapted.

---

## Summary verdict

1. **Two Canonical Paradigms Exist in Rodents:**
   - **Rockwood Deficit Accumulation Model (Frailty Index, FI):** Continuous score ($0.0 \le \mathrm{FI} \le 1.0$) calculating the proportion of accumulated health deficits across multiple physiological systems. The gold standard mouse adaptation is the **Whitehead & Howlett 31-item Clinical Frailty Index** ([Whitehead et al., 2014](https://doi.org/10.1093/gerona/glt136)), which evaluates noninvasive clinical signs (integument, musculoskeletal, vestibulocochlear, ocular/nasal, digestive, urogenital, respiratory, discomfort, body weight, temperature).
   - **Fried Physical Frailty Phenotype (FP):** Categorical classification (non-frail, prefrail, frail) based on five phenotypic domains (unintentional weight loss, weakness, slowness, poor endurance/exhaustion, and low physical activity). The primary mouse translation is the **Liu & Thompson 5-item Mouse Physical Frailty Phenotype** ([Liu et al., 2014](https://doi.org/10.1093/gerona/glu008); [Graber et al., 2015](https://doi.org/10.1093/gerona/glu204)), requiring physical tests (grip meter, rotarod, treadmill fatigue, voluntary running wheel, body weight).

2. **The Published 8-Item Battery in Mouse Literature:**
   - A specific 8-item mouse frailty battery **does exist** in the primary literature: the **Parks & Whitehead 8-Item Performance-Based Frailty Index** ([Parks et al., 2012](https://doi.org/10.1093/gerona/glr193); [Whitehead et al., 2014](https://doi.org/10.1093/gerona/glt136)).
   - It was derived via factor analysis over 31 physiological parameters and consists of **7 open-field centroid tracking measures + 1 body weight measure**:
     1. *Total distance moved (cm in 10 min)*
     2. *Maximal distance moved between bouts of inactivity (cm)*
     3. *Total duration of movement (seconds)*
     4. *Percent of total time spent moving (%)*
     5. *Meander (change in direction per unit distance moved, deg/cm, 0°–180°)*
     6. *Average velocity of movement (cm/s)*
     7. *Rearing frequency (occurrences / 10 min)*
     8. *Body weight (g)*
   - *Limitations noted by the authors:* Because 4 of the 8 items measure movement quantity/speed, this reduced battery suffers from higher variance, ceiling effects in older animals, and lacks multi-system coverage compared to the 31-item clinical FI.

3. **What Top-View SuperAnimal Pose (27 Keypoints) Can vs. Cannot Measure:**
   - **Can measure directly from open field:** Centroid path length, mean/active speed, immobility fraction, pause bout frequency, thigmotaxis fraction (`frac_near` arena wall), meander/heading tortuosity, axial body elongation (kyphosis/hunched posture proxy), and movement velocity variability (IQR/CV).
   - **Cannot measure without external assays:** Grip strength (needs grip meter / grid hang), treadmill endurance (needs motorized treadmill), voluntary long-term physical activity (needs home-cage running wheel), scale body weight, core/surface temperature (needs thermometer/IR camera), ocular/auditory deficits (cataracts, corneal opacity, clicker reflex), integument deficits (alopecia, whisker loss, dermatitis), and ventral paw strike/force kinetics (needs CatWalk/DigiGait or force plates).

4. **Recommended 8-Feature Table for OpenEthoMaze Open-Field Assay:**
   - Adapts the literature-backed Parks/Whitehead metrics into a **100% video-derivable 8-feature kinematics battery** by replacing external scale weight and error-prone top-view 2D rearing with validated spatial (`thigmotaxis_frac`) and postural/kinematic (`body_elongation_mean`, `speed_iqr_cms`) markers.

---

## 1. Canonical frailty-index constructions in rodents

Frailty represents a state of heightened vulnerability to stressors resulting from age-related physiological decline across multiple organ systems.

| Framework | Core Concept | Human Origin | Key Rodent Adaptation | Primary Metrics / Grain |
|-----------|--------------|--------------|-----------------------|-------------------------|
| **Deficit Accumulation (Frailty Index, FI)** | Continuous ratio ($0.0–1.0$): deficits present divided by total deficits evaluated. Requires $\ge 30–40$ variables across diverse organ systems. | Mitnitski et al. (2001); [Searle et al. (2008)](https://doi.org/10.1186/1471-2318-8-24) | **Whitehead 31-item Clinical FI** ([Whitehead et al., 2014](https://doi.org/10.1093/gerona/glt136)) | 31 noninvasive clinical signs scored $0, 0.5, 1.0$ across 8 organ systems + weight & temperature. |
| **Physical Frailty Phenotype (FP)** | Categorical syndrome: Frail ($\ge 3$ criteria), Prefrail ($1–2$), Non-frail ($0$). Focuses on energy metabolism and musculoskeletal reserve. | [Fried et al. (2001)](https://doi.org/10.1093/gerona/56.3.m146) (Cardiovascular Health Study) | **Liu 5-item Mouse FP** ([Liu et al., 2014](https://doi.org/10.1093/gerona/glu008); [Graber et al., 2015](https://doi.org/10.1093/gerona/glu204)) | Grip strength, rotarod speed, treadmill endurance, wheel running, body weight (bottom/top 20% cutoffs). |
| **Performance-Based 8-Item FI** | Reduced deficit index using 7 open-field locomotion variables + body weight. Graded deficit scoring against young reference cohorts ($0, 0.25, 0.5, 0.75, 1.0$). | Derived from exploratory factor analysis of mouse deficit models. | **Parks & Whitehead 8-item FI** ([Parks et al., 2012](https://doi.org/10.1093/gerona/glr193); [Whitehead et al., 2014](https://doi.org/10.1093/gerona/glt136)) | 10 min open field tracking (distance, speed, immobility, meander, rearing, pause distance) + scale weight. |
| **Machine-Vision Visual FI (vFI)** | Machine learning regression (Random Forest) predicting 31-item manual clinical FI scores from automated video pose and tracking features. | Reverse-translates human clinical frailty prediction from movement sensors. | **JAX vFI / FRIGHT Clock** ([Hession et al., 2022/2023](https://doi.org/10.1038/s43587-022-00266-0); [Kane et al., 2020](https://doi.org/10.1093/gerona/glz244)) | 44–59 engineered pose, gait, and open-field features from top-down video (12-point pose model). |

---

## 2. Typical item counts and clinical domains

### The Canonical 31-Item Mouse Clinical Frailty Index (Whitehead & Howlett)

The most widely cited and validated preclinical frailty tool is the **31-item Clinical Frailty Index** ([Whitehead et al., 2014](https://doi.org/10.1093/gerona/glt136); [Feridooni et al., 2015](https://doi.org/10.1093/gerona/glu161); [Kane et al., 2019](https://doi.org/10.1016/j.exger.2019.03.007)). An experienced examiner completes the assessment noninvasively in ~3–5 minutes per mouse.

#### Scoring Rubric
- **Ordinal clinical signs:** $0 = \text{no deficit}$, $0.5 = \text{moderate deficit}$, $1.0 = \text{severe deficit}$.
- **Continuous metrics (Weight & Surface Temperature):** Scored relative to young adult reference standard deviations ($\text{SD}$):
  - Difference $< 1\,\text{SD} \implies 0$
  - Difference $\pm 1\,\text{SD} \implies 0.25$
  - Difference $\pm 2\,\text{SD} \implies 0.50$
  - Difference $\pm 3\,\text{SD} \implies 0.75$
  - Difference $> 3\,\text{SD} \implies 1.00$
- **Total Index Calculation:**
  $$\mathrm{FI} = \frac{\sum_{i=1}^{31} \text{score}_i}{31}$$

#### Item Breakdown by Organ System

| System / Domain | Clinical Item | Deficit Description / Scoring Criteria |
|-----------------|---------------|----------------------------------------|
| **1. Integument** | 1. Alopecia | Hair loss / balding / barbering ($0 = \text{none}$, $0.5 = <25\%$, $1.0 = >25\%$) |
| | 2. Loss of fur color | Graying or browning of black coat ($0 = \text{black}$, $0.5 = \text{patchy}$, $1.0 = \text{diffuse gray}$) |
| | 3. Dermatitis | Skin erosion, ulceration, scratching sores ($0 = \text{absent}$, $0.5 = \text{focal}$, $1.0 = \text{widespread}$) |
| | 4. Loss of whiskers | Absence/shortening of vibrissae ($0 = \text{intact}$, $0.5 = \text{partial loss}$, $1.0 = \text{absent}$) |
| | 5. Coat condition | Ungroomed/matted/ruffled fur ($0 = \text{smooth/shiny}$, $0.5 = \text{slightly ruffled}$, $1.0 = \text{matted/unkempt}$) |
| **2. Musculoskeletal** | 6. Tumors | Palpable/visible subcutaneous masses ($0 = \text{absent}$, $0.5 = <1\,\text{cm}^3$, $1.0 = >1\,\text{cm}^3$) |
| | 7. Distended abdomen | Fluid/organ enlargement ($0 = \text{normal}$, $0.5 = \text{mild distension}$, $1.0 = \text{marked distension}$) |
| | 8. Kyphosis | Exaggerated dorsal curvature / hunched posture ($0 = \text{flat spine}$, $0.5 = \text{mild hump}$, $1.0 = \text{severe hunch}$) |
| | 9. Tail stiffening | Rigidity/inability of tail to curl or wrap when stroked ($0 = \text{pliant}$, $0.5 = \text{stiff}$, $1.0 = \text{rigid}$) |
| | 10. Gait disorders | Wobbling, wide stance, dragging limbs, hopping ($0 = \text{normal}$, $0.5 = \text{mild limp/ataxia}$, $1.0 = \text{severe impairment}$) |
| | 11. Tremor | Involuntary body oscillation at rest/motion ($0 = \text{absent}$, $0.5 = \text{mild/intermittent}$, $1.0 = \text{constant/severe}$) |
| | 12. Forelimb grip strength | Resistance to backward pull on cage wire lid ($0 = \text{strong sustained grip}$, $0.5 = \text{weak grip}$, $1.0 = \text{no grip}$) |
| | 13. Body condition score (BCS) | Muscle wasting over sacroiliac/spine ($0 = \text{BCS 3}$, $0.5 = \text{BCS 2 or 4}$, $1.0 = \text{BCS 1 or 5}$) |
| **3. Vestibulocochlear & Neurological** | 14. Vestibular disturbance | Circling, head tilting, barrel rolling, abnormal righting ($0 = \text{absent}$, $0.5 = \text{mild tilt}$, $1.0 = \text{circling/loss of balance}$) |
| | 15. Hearing loss | Preyer reflex / startle to sudden auditory click ($0 = \text{reacts } 3/3$, $0.5 = \text{reacts } 1\text{–}2/3$, $1.0 = \text{no response}$) |
| | 16. Head tilt | Deviation of head from normal horizontal plane ($0 = \text{none}$, $0.5 = \text{moderate}$, $1.0 = \text{severe}$) |
| **4. Ocular & Nasal** | 17. Cataracts | Opacification/clouding of the lens ($0 = \text{clear}$, $0.5 = \text{unilateral/mild}$, $1.0 = \text{bilateral dense white}$) |
| | 18. Corneal opacity | Cloudiness/white spots on cornea ($0 = \text{clear}$, $0.5 = \text{focal cloudy}$, $1.0 = \text{complete opacity}$) |
| | 19. Eye discharge / swelling | Exophthalmos, crusting, blepharitis, squinting ($0 = \text{clean}$, $0.5 = \text{mild periocular crust}$, $1.0 = \text{swollen/closed}$) |
| | 20. Microphthalmia | Sunken or abnormally small eyes ($0 = \text{normal}$, $0.5 = \text{mild sunken}$, $1.0 = \text{severe microphthalmia}$) |
| | 21. Vision loss | Visual placing reflex when lowered toward surface ($0 = \text{extends forepaws early}$, $0.5 = \text{delayed}$, $1.0 = \text{no extension}$) |
| | 22. Menace reflex | Blinking to approaching object without touching vibrissae ($0 = \text{brisk blink}$, $0.5 = \text{sluggish}$, $1.0 = \text{absent}$) |
| | 23. Nasal discharge | Serous, mucoid, or bloody discharge from nares ($0 = \text{clean}$, $0.5 = \text{mild wetness}$, $1.0 = \text{heavy crust/discharge}$) |
| **5. Digestive & Urogenital** | 24. Malocclusion | Overgrown or deviated incisors ($0 = \text{normal bite}$, $0.5 = \text{mild overgrowth}$, $1.0 = \text{curved into palate}$) |
| | 25. Rectal prolapse | Eversion of rectal mucosa ($0 = \text{absent}$, $0.5 = \text{mild protrusion}$, $1.0 = \text{severe exteriorized tissue}$) |
| | 26. Urogenital prolapse | Penile/uterine/vaginal prolapse ($0 = \text{absent}$, $0.5 = \text{partial}$, $1.0 = \text{severe}$) |
| | 27. Diarrhea / fecal staining | Perianal fecal soiling or wet loose stool ($0 = \text{normal pellets}$, $0.5 = \text{loose feces/soiling}$, $1.0 = \text{severe liquid diarrhea}$) |
| **6. Respiratory** | 28. Breathing rate / depth | Dyspnea, tachypnea, labored respiration, wheezing ($0 = \text{regular eupnea}$, $0.5 = \text{mild tachypnea}$, $1.0 = \text{labored gasping}$) |
| **7. Discomfort** | 29. Mouse Grimace Scale / Piloerection | Orbital tightening, nose bulge, cheek bulge, ear position, spiky hair ($0 = \text{relaxed}$, $0.5 = \text{moderate}$, $1.0 = \text{severe}$) |
| **8. Systemic / Vital** | 30. Body surface temperature | Infrared thermometry on dorsum/flank ($\text{SD}$ difference from young reference) |
| | 31. Body weight | Total mass on scale ($\text{SD}$ difference from young adult reference) |

---

## 3. The published 8-item mouse frailty battery

### Historical Genesis: Parks et al. (2012) & Whitehead et al. (2014)

In the pioneering work establishing rodent deficit accumulation ([Parks et al., 2012](https://doi.org/10.1093/gerona/glr193)), Howlett and colleagues initially developed a 31-item physiological battery requiring blood gases, dual-energy X-ray absorptiometry (DEXA), and hemodynamics. To make frailty assessment accessible without terminal blood draws or anesthesia, they conducted **exploratory factor analysis with varimax rotation**.

This analysis identified **activity levels** and **body weight** as the primary noninvasive factors explaining variance. They extracted **eight specific parameters** to form the **"Performance-Based 8-Item Frailty Index"**:

```
Parks / Whitehead 8-Item Frailty Battery:
├── 1. Total distance moved (cm in 10 min)
├── 2. Maximum distance moved between bouts of inactivity (cm)
├── 3. Total duration of movement (seconds)
├── 4. Percent of total time spent moving (%)
├── 5. Meander (degrees / cm; range 0° to 180°)
├── 6. Average velocity of movement (cm/s)
├── 7. Rearing frequency (counts in 10 min)
└── 8. Body weight (grams)
```

### Protocol & Deficit Scoring in the Original Literature
- **Apparatus:** $43.5 \times 21.5\,\text{cm}$ or $40 \times 40\,\text{cm}$ open-field arena.
- **Duration:** 10 minutes (typically 10:00 AM – 12:00 PM).
- **Tracking:** Overhead camera tracking the 2D center point of the animal (originally EthoVision).
- **Scoring Method:** Each animal's 8 metrics are compared to a reference distribution of young adult mice (e.g. 3–5 months old). Values deviating by $\pm 1\,\text{SD}$ score $0.25$; $\pm 2\,\text{SD}$ score $0.50$; $\pm 3\,\text{SD}$ score $0.75$; $>3\,\text{SD}$ score $1.00$. Summed and divided by 8.

### Critical Evaluation & Known Limitations of the 8-Item Battery

Subsequent studies ([Whitehead et al., 2014](https://doi.org/10.1093/gerona/glt136); [Geier et al., 2025](https://doi.org/10.18632/aging.206307)) evaluated the 8-item index against the 31-item clinical index and reported key findings:
1. **High Collinearity:** 4 of the 8 variables (`total_distance`, `velocity`, `movement_duration`, `percent_time_moving`) measure nearly identical facets of locomotor quantity.
2. **Ceiling Effect:** Unlike the human 70-item FI or mouse 31-item clinical FI (which scale smoothly up to $\mathrm{FI} \approx 0.40–0.60$ at 28 months), the 8-item index jumped sharply from 5 months ($\mathrm{FI} \approx 0.06$) to 19 months ($\mathrm{FI} \approx 0.36$) and plateaued at 28 months ($\mathrm{FI} \approx 0.38$).
3. **Reference Sensitivity:** Because it relies entirely on distance/speed deviations, variations in arena size, lighting, or strain shift the threshold, making uncalibrated inter-cohort comparisons noisy.
4. **Conclusion:** While the 8-item battery is a valid **locomotor vitality / performance index**, it should be distinguished from a multi-system clinical deficit accumulation index.

---

## 4. Top-view SuperAnimal pose (27 keypoints): capabilities & limitations

When working with top-down overhead video analyzed by DeepLabCut's **SuperAnimal TopViewMouse** model ([Ye et al., 2024](https://doi.org/10.1038/s41467-024-48792-2)), the model extracts **27 keypoints**:
- *Head & Sensory:* `nose`, `left_eye`, `right_eye`, `left_ear`, `right_ear`, `left_ear_tip`, `right_ear_tip`, `head_midpoint`
- *Axial Spine & Trunk:* `neck`, `mid_back`, `mouse_center`, `mid_backend`, `mid_backend2`, `mid_backend3`, `tail_base`
- *Tail:* `tail1`, `tail2`, `tail3`, `tail4`, `tail5`, `tail_end`
- *Lateral Body Contour:* `left_shoulder`, `left_midside`, `left_hip`, `right_shoulder`, `right_midside`, `right_hip`

```
Top-View Keypoint Topology (SuperAnimal TopViewMouse, 27 kpts):

              (nose)
             /      \
      (L_eye)        (R_eye)
      (L_ear)        (R_ear)
             \      /
              (neck)
             /      \
 (L_shoulder) |      | (R_shoulder)
 (L_midside)  (center) (R_midside)
 (L_hip)      |      | (R_hip)
           (tail_base)
                |
          (tail1 - tail5)
                |
            (tail_end)
```

### What CAN Be Extracted from Top-View Pose Kinematics

| Kinematic Domain | Mathematical / Operational Definition | Literature Anchor | Frailty / Aging Relevance |
|------------------|----------------------------------------|-------------------|---------------------------|
| **1. Cumulative Distance (Path Length)** | $\sum_{t=1}^T \|\mathbf{x}_t - \mathbf{x}_{t-1}\|$ over smoothed `mouse_center` | Parks #1; Whitehead #1 | Overall locomotor activity, exploration drive, metabolic vigor. |
| **2. Mean / Active Speed** | $\frac{1}{|T_{\text{active}}|}\sum_{t \in T_{\text{active}}} v_t$ ($v_t \ge 1.0\,\text{cm/s}$) | Parks #6; Whitehead #6; Liu slowness proxy | Movement speed during locomotion; drops reliably with age and sarcopenia. |
| **3. Immobility Fraction** | Fraction of frames where centroid velocity $v_t < v_{\text{thresh}}$ (e.g. $<0.5\,\text{cm/s}$) | Parks #3, #4; Gerós standstill | Sedentary state; proxy for Fried exhaustion / low physical activity. |
| **4. Pause / Inactivity Bout Dynamics** | Number of distinct immobility bouts ($\ge 0.5\,\text{s}$) or max travel between pauses | Parks #2; Takahashi pausing; Goñi-Erro arrest | Motor hesitation, fragmentation of locomotion, cognitive appraisal pauses. |
| **5. Thigmotaxis Fraction (`frac_near`)** | Proportion of time spent within boundary zone (e.g. outer $10\%\text{–}15\%$ margin) | Standard OFT; JAX vFI periphery time ([Hession et al., 2022](https://doi.org/10.1038/s43587-022-00266-0)) | Exploratory confidence vs agoraphobia / anxiety; frail mice cling to walls. |
| **6. Meander / Path Tortuosity** | $\frac{\sum |\Delta \theta_t|}{\text{Total Distance}}$ ($\text{deg/cm}$, heading change per cm) | Parks #5; Whitehead #5 | Motor coordination, ataxia, spatial search efficiency. |
| **7. Body Elongation / Kyphosis Proxy** | Distance between `nose` and `tail_base` (or ratio of spine length to perimeter) | JAX vFI morphometrics; Whitehead #8 (kyphosis) | Contracted/hunched body posture vs extended gait posture; spine deformation. |
| **8. Speed Variability / Irregularity** | Interquartile range ($\text{IQR}$) or Coefficient of Variation ($\text{CV}$) of velocity | JAX vFI gait features ([Hession et al., 2022](https://doi.org/10.1038/s43587-022-00266-0)) | Kinematic instability, loss of smooth cruising velocity, gait irregularity. |

### What CANNOT Be Extracted (Requires Ancillary Assays)

1. **Neuromuscular Force & Endurance:**
   - *Grip strength* (requires digital force dynamometer or wire inverted-cling screen).
   - *Treadmill running endurance to exhaustion* (requires enclosed motorized lane treadmill).
   - *Voluntary circadian physical activity* (requires running-wheel home cage).
2. **Integument & Dermatological Signs:**
   - *Alopecia, barbering, whisker loss, dermatitis, loss of fur color, piloerection* (requires close manual physical exam / macro photography).
3. **Sensory & Cranial Deficits:**
   - *Cataracts, corneal clouding, microphthalmia, eye discharge/swelling* (requires slit-lamp / ophthalmic inspection).
   - *Hearing loss* (requires calibrated acoustic clicker for Preyer reflex).
   - *Menace / visual placing reflex* (requires manual tail suspension test).
4. **Deep Clinical & Systemic Signs:**
   - *Malocclusion, rectal/vaginal prolapse, Mouse Grimace Scale facial action units* (requires close oral/perianal exam and specialized facial-view cameras).
   - *Body weight* (requires calibrated precision balance).
   - *Body temperature* (requires infrared rectal/cutaneous thermometer).
5. **Ventral Footfall & Ground Reaction Kinetics:**
   - *Individual paw contact strike/liftoff, duty factor, step width, swing/stance duration, paw pressure* (SuperAnimal TopViewMouse tracks dorsal joints/silhouette; ventral footfalls require bottom-view CatWalk, DigiGait, or transparent-floor ventral video).

---

## 5. Recommended 8-feature open-field frailty table (OpenEthoMaze)

To evaluate frailty-related phenotypes from open-field tracking in OpenEthoMaze (using binned time intervals from `mouse_center` and 27-keypoint SuperAnimal pose), we recommend the following **8-Feature Open-Field Kinematic Battery**.

This table retains the core locomotor dynamics of the canonical **Parks/Whitehead 8-item battery** while modernizing it into a **100% automated, video-derivable specification**:

| Column Name | Metric Label | Unit | Operational Definition | Target Frailty Construct | Literature Anchor |
|-------------|--------------|------|------------------------|--------------------------|-------------------|
| `path_length_cm` | Cumulative Distance | $\text{cm}$ | Total trajectory length of `mouse_center` over the interval ($5\,\text{min}$ or $10\,\text{min}$) | Locomotor capacity / Vitality deficit | Parks #1; Whitehead #1; Liu slowness proxy |
| `mean_active_speed_cms` | Mean Active Speed | $\text{cm/s}$ | Mean velocity during moving epochs ($\|\Delta \mathbf{x}\| / \Delta t \ge 1.0\,\text{cm/s}$) | Locomotor vigor / Sarcopenia | Parks #6; Whitehead #6; Fried slowness |
| `immobility_frac` | Immobility Fraction | Ratio $[0, 1]$ | Proportion of frames with velocity $< 0.5\,\text{cm/s}$ | Exhaustion / Physical inactivity | Parks #3, #4; Fried low activity; Gerós standstill |
| `pause_bout_count` | Pause / Arrest Frequency | Count | Number of discrete stationary bouts ($\text{speed} < 0.5\,\text{cm/s}$, $\text{duration} \ge 0.5\,\text{s}$) | Motor fragmentation / Hesitation | Parks #2; Takahashi pausing; Goñi-Erro arrest |
| `thigmotaxis_frac` | Thigmotaxis (`frac_near`) | Ratio $[0, 1]$ | Fraction of time `mouse_center` is within the outer boundary zone ($10\%\text{–}15\%$ perimeter) | Exploratory confidence / Avoidance | JAX vFI periphery time; Standard OFT anxiety |
| `meander_deg_cm` | Path Meander / Tortuosity | $\text{deg/cm}$ | Absolute heading direction change divided by distance moved ($\sum \|\Delta \theta\| / D$) | Motor coordination / Ataxia | Parks #5; Whitehead #5; JAX vFI meander |
| `body_elongation_mean` | Body Elongation (Kyphosis) | $\text{cm}$ | Mean Euclidean distance between `nose` and `tail_base` during active locomotion | Kyphosis / Musculoskeletal posture | Whitehead #8 (kyphosis); JAX vFI morphometrics |
| `speed_iqr_cms` | Speed Dispersion (IQR) | $\text{cm/s}$ | Interquartile range of velocity across all interval frames ($\text{P}_{75} - \text{P}_{25}$) | Motor control irregularity / Gait instability | JAX vFI speed IQR; Stride-level variability |

### Rationale for Feature Swaps relative to Parks/Whitehead 8-Item List:
1. **Replacement of Body Weight (`body_weight`):**
   - In Parks/Whitehead, weight was measured on a physical scale. Replacing it with `thigmotaxis_frac` keeps the battery entirely within the automated video pipeline while capturing exploratory boldness vs. agoraphobia. (If physical scale weight is recorded during session setup, it can be appended as an optional 9th metadata column).
2. **Replacement of 2D Rearing Frequency (`rearing_frequency`):**
   - Top-down 2D camera tracking produces false positives on rearing (a hunched mouse often produces similar contour shrinkage as a rear). Replacing it with `body_elongation_mean` (mean nose-to-tailbase length) and `speed_iqr_cms` directly measures spine curvature (kyphosis proxy) and kinematic motor control irregularity with verified keypoint geometry.
3. **Consolidation of Collinear Movement Scalars:**
   - In Parks/Whitehead, four metrics measured movement amount (`distance`, `duration`, `% time moving`, `velocity`). We consolidate this into `path_length_cm` (total output), `mean_active_speed_cms` (peak capability), `immobility_frac` (inactivity proportion), and `pause_bout_count` (temporal bout structure).

---

## 6. Implementation & Verification (V&V) Guidelines

When calculating these 8 features in OpenEthoMaze:
- **Smoothing Invariant:** Always apply median filtering or low-pass smoothing (e.g. $5\,\text{Hz}$ cut-off or rolling 3-frame median) to raw 2D keypoint coordinates prior to differentiation. Raw keypoint jitter inflates `path_length_cm` and corrupts `meander_deg_cm`.
- **Litmus Test (Identity / Invariance):**
  - Stationary synthetic test data (zero mouse movement) must evaluate to: `path_length_cm == 0.0`, `mean_active_speed_cms == NaN` (or 0.0), `immobility_frac == 1.0`, `pause_bout_count == 1`, `meander_deg_cm == 0.0`, `speed_iqr_cms == 0.0`.
  - Constant straight-line motion at $10\,\text{cm/s}$ must evaluate to: `meander_deg_cm == 0.0`, `immobility_frac == 0.0`, `pause_bout_count == 0`, `mean_active_speed_cms == 10.0`.
- **Scoring Reference:** To generate a composite Frailty Index score ($0.0–1.0$) from these 8 features, compute $z$-scores or quantile deviation relative to a young adult control cohort (e.g., $10\text{–}16$ weeks old), assigning graded deficit values ($0, 0.25, 0.50, 0.75, 1.00$) following the Parks/Whitehead standard deviation bands.

---

## 7. Primary literature references

1. **Searle SD, Mitnitski A, Gahbauer EA, Gill TM, Rockwood K.** (2008). *A standard procedure for creating a frailty index based on deficit accumulation.* BMC Geriatrics, 8:24. [DOI: 10.1186/1471-2318-8-24](https://doi.org/10.1186/1471-2318-8-24). PMID: 18826625.
2. **Fried LP, Tangen CM, Walston J, Newman AB, Hirsch C, Gottdiener J, Seeman T, Tracy R, Kop WJ, Burke G, McBurnie MA.** (2001). *Frailty in older adults: evidence for a phenotype.* The Journals of Gerontology: Series A, 56(3):M146–M156. [DOI: 10.1093/gerona/56.3.m146](https://doi.org/10.1093/gerona/56.3.m146). PMID: 11253156.
3. **Parks RJ, Fares E, Macdonald JK, Ernst MC, Sinal CJ, Rockwood K, Howlett SE.** (2012). *A procedure for creating a frailty index based on deficit accumulation in aging mice.* The Journals of Gerontology: Series A, 67(3):217–227. [DOI: 10.1093/gerona/glr193](https://doi.org/10.1093/gerona/glr193). PMID: 22021390.
4. **Whitehead JC, Hildebrand BA, Sun M, Rockwood MR, Rose RA, Rockwood K, Howlett SE.** (2014). *A clinical frailty index in aging mice: comparisons with frailty index data in humans.* The Journals of Gerontology: Series A, 69(6):621–632. [DOI: 10.1093/gerona/glt136](https://doi.org/10.1093/gerona/glt136). PMID: 24149437. PMCID: PMC4022099.
5. **Liu H, Graber TG, Ferguson-Stegall L, Thompson LV.** (2014). *Clinically relevant frailty index for mice.* The Journals of Gerontology: Series A, 69(12):1485–1491. [DOI: 10.1093/gerona/glu008](https://doi.org/10.1093/gerona/glu008). PMID: 25164899.
6. **Graber TG, Ferguson-Stegall L, Kim JH, Thompson LV.** (2015). *Longitudinal analysis of physical frailty in male C57BL/6J mice.* The Journals of Gerontology: Series A, 70(11):1377–1386. [DOI: 10.1093/gerona/glu204](https://doi.org/10.1093/gerona/glu204). PMID: 25422476.
7. **Feridooni HA, Sun MH, Rockwood K, Howlett SE.** (2015). *Reliability of a Frailty Index Based on the Clinical Assessment of Health Deficits in Male C57BL/6J Mice.* The Journals of Gerontology: Series A, 70(6):686–693. [DOI: 10.1093/gerona/glu161](https://doi.org/10.1093/gerona/glu161). PMID: 25253574.
8. **Kane AE, Hilmer SN, Mach J, Mitchell SJ, de Cabo R, Howlett SE.** (2019). *Animal models of frailty: current applications in clinical research.* Experimental Gerontology, 121:24–34. [DOI: 10.1016/j.exger.2019.03.007](https://doi.org/10.1016/j.exger.2019.03.007). PMID: 30904533.
9. **Kane AE, Keller A, Heinze-Milne S, Grandy SA, Howlett SE.** (2020). *A machine learning approach to determine characteristics of long-lived mice and evaluate frailty index data.* The Journals of Gerontology: Series A, 75(6):1057–1065. [DOI: 10.1093/gerona/glz244](https://doi.org/10.1093/gerona/glz244). PMID: 31633758.
10. **Hession LE, Sabnis GS, Churchill GA, Kumar V.** (2022/2023). *A machine-vision-based frailty index for mice.* Nature Aging, 2(8):756–766. [DOI: 10.1038/s43587-022-00266-0](https://doi.org/10.1038/s43587-022-00266-0). PMCID: PMC10117690.
11. **Geier JA, et al.** (2025). *Analysis of the current state of frailty indexes and their implementation for aging intervention studies.* Aging (Albany NY), 17(1):15–32. [DOI: 10.18632/aging.206307](https://doi.org/10.18632/aging.206307). PMID: 39868779.
12. **Ye S, et al.** (2024). *SuperAnimal pretrained pose estimation models for behavioral analysis.* Nature Communications, 15:48792. [DOI: 10.1038/s41467-024-48792-2](https://doi.org/10.1038/s41467-024-48792-2).
