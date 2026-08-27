"""NOR protocol prologue — mean/interval cousins only (no rank tests).

Builds a self-contained run folder from original-investigation DR and presence
artifacts. Protocol claims are one-sample t within sex (F and M separately;
txs pooled within sex). Treatment coda is within-sex Welch ANOVA
(Alexander–Govern). Association is Pearson within sex.

Question: Does the NOR protocol move engagement and novel preference, even
when treatment arms do not separate on those scalars?
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_presence import animal_median_across_models  # noqa: E402
from nor_object_mi.simpler_first_q1 import SEX_ORDER, anova_within_sex  # noqa: E402

PHASES = ("NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr")
STEPS = ("no_obj->identical", "identical->novel", "no_obj->novel")
PRESENCE_METRICS = (
    "delta_frac_near",
    "delta_mean_dist_any_m",
    "delta_shannon_bits",
    "delta_richness",
)
DR_METRICS = ("dr_original", "dr_object_prox")
ASSOC_Y = (("dr_object_prox", "original_vs_object_prox"),)
# Movement bout vs syllable bout clocks (not DR↔ambulation).
# Syllable NOR ladders have count/duration only — no bout speed / immobile.
CLOCK_PAIRS = (
    ("n_move_bouts", "n_syll_bouts", "n_move_vs_n_syll", "two_clocks"),
    ("median_move_duration_s", "median_syll_duration_s", "dur_move_vs_dur_syll", "two_clocks"),
    ("median_move_speed_mps", "session_mean_speed_mps", "bout_speed_vs_session_speed", "move_litmus"),
    ("sum_move_distance_m", "session_distance_m", "bout_dist_vs_session_dist", "move_litmus"),
)

DEFAULT_CLASSIC = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_classic_dr\classic_dr_paired.csv"
)
DEFAULT_PRESENCE = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_presence_steps\presence_step_deltas_per_animal.csv"
)
DEFAULT_DISPERSION = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_presence_steps\presence_step_across_model_dispersion.csv"
)
DEFAULT_DISPERSION_SUMMARY = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_presence_steps\presence_step_across_model_dispersion_summary.csv"
)
DEFAULT_CLOCKS = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_ambulation_clocks\clock_metrics_per_animal.csv"
)
DEFAULT_OUT = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_protocol_prologue"
)


def ttest_one_sample(values: np.ndarray) -> dict[str, object]:
    """One-sample Student t vs 0 (mean/interval cousin of Wilcoxon on Δ)."""
    d = np.asarray(values, dtype=np.float64)
    d = d[np.isfinite(d)]
    n = int(d.size)
    if n < 2:
        return {
            "n": n,
            "mean_delta": float("nan"),
            "median_delta": float("nan"),
            "frac_gt0": float("nan"),
            "stat": float("nan"),
            "p": float("nan"),
            "test": "ttest_1samp",
        }
    res = stats.ttest_1samp(d, popmean=0.0, alternative="two-sided")
    return {
        "n": n,
        "mean_delta": float(np.mean(d)),
        "median_delta": float(np.median(d)),
        "frac_gt0": float(np.mean(d > 0)),
        "stat": float(res.statistic),
        "p": float(res.pvalue),
        "test": "ttest_1samp",
    }


def ttest_paired(a: np.ndarray, b: np.ndarray) -> dict[str, object]:
    """Paired Student t: mean(a − b) vs 0."""
    aa = np.asarray(a, dtype=np.float64)
    bb = np.asarray(b, dtype=np.float64)
    ok = np.isfinite(aa) & np.isfinite(bb)
    n = int(ok.sum())
    if n < 2:
        return {
            "n": n,
            "mean_delta": float("nan"),
            "median_delta": float("nan"),
            "frac_gt0": float("nan"),
            "stat": float("nan"),
            "p": float("nan"),
            "test": "ttest_rel",
        }
    diff = aa[ok] - bb[ok]
    res = stats.ttest_rel(aa[ok], bb[ok], alternative="two-sided")
    return {
        "n": n,
        "mean_delta": float(np.mean(diff)),
        "median_delta": float(np.median(diff)),
        "frac_gt0": float(np.mean(diff > 0)),
        "stat": float(res.statistic),
        "p": float(res.pvalue),
        "test": "ttest_rel",
    }


def pearson_pair(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Pearson r on finite pairs. Litmus: identical series → r = 1."""
    xx = np.asarray(x, dtype=np.float64)
    yy = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(xx) & np.isfinite(yy)
    n = int(ok.sum())
    if n < 3:
        return {"n": float(n), "pearson_r": float("nan"), "p": float("nan")}
    r, p = stats.pearsonr(xx[ok], yy[ok])
    return {"n": float(n), "pearson_r": float(r), "p": float(p)}


def _hit(p: float) -> bool:
    return bool(np.isfinite(p) and p < 0.05)


def _sex_slices(g: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    out: list[tuple[str, pd.DataFrame]] = [("all", g)]
    for sex in SEX_ORDER:
        out.append((sex, g[g["sex"] == sex]))
    return out


def build_dr_tables(paired: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Animal DR table + one-sample / paired t / Welch ANOVA + Pearson."""
    animals = paired.copy()
    animals = animals.rename(
        columns={
            "dr_classic": "dr_original",
            "dr_classic_minus_object_prox": "dr_original_minus_object_prox",
        }
    )
    keep = [
        "animal_id",
        "sex",
        "tx",
        "phase_layer",
        "t_fam_s",
        "t_nvl_s",
        "dr_original",
        "dr_object_prox",
        "frac_near_fam",
        "frac_near_nvl",
        "mean_speed_mps",
        "time_immobile_s",
        "distance_m",
        "dr_original_minus_object_prox",
    ]
    animals = animals[keep].copy()
    animals["phase_layer"] = pd.Categorical(animals["phase_layer"], categories=list(PHASES), ordered=True)
    animals = animals.sort_values(["phase_layer", "animal_id"]).reset_index(drop=True)

    test_rows: list[dict[str, object]] = []
    for phase, g in animals.groupby("phase_layer", observed=True):
        for sex, gs in _sex_slices(g):
            grain = (
                "animal × phase × novel_obj (txs pooled, within sex)"
                if sex != "all"
                else "animal × phase × novel_obj (txs pooled, sexes pooled)"
            )
            for metric in DR_METRICS:
                rec = ttest_one_sample(gs[metric].to_numpy())
                test_rows.append(
                    {
                        "phase_layer": str(phase),
                        "question": "novel_preference",
                        "metric": metric,
                        "grain": grain,
                        "sex": sex,
                        "step": "",
                        "hit_p05": _hit(float(rec["p"])),
                        "consensus": (
                            "median across 21 kpMS models"
                            if metric == "dr_object_prox"
                            else "none (original investigation export)"
                        ),
                        **rec,
                    }
                )
            # Complementary: absolute investigation times (seconds), not DR.
            rec_t = ttest_paired(gs["t_nvl_s"].to_numpy(), gs["t_fam_s"].to_numpy())
            test_rows.append(
                {
                    "phase_layer": str(phase),
                    "question": "fam_vs_nvl_investigation_s",
                    "metric": "t_nvl_minus_t_fam_s",
                    "grain": grain,
                    "sex": sex,
                    "step": "",
                    "hit_p05": _hit(float(rec_t["p"])),
                    "consensus": "none (original investigation export)",
                    **rec_t,
                }
            )

        anova_g = g
        for metric in DR_METRICS:
            anova = anova_within_sex(anova_g, metric=metric)
            for _, row in anova.iterrows():
                test_rows.append(
                    {
                        "phase_layer": str(phase),
                        "question": "tx_on_dr",
                        "metric": metric,
                        "grain": "animal × phase × novel_obj (within sex)",
                        "sex": str(row["sex"]),
                        "step": "",
                        "n": int(row["n"]),
                        "mean_delta": float("nan"),
                        "median_delta": float("nan"),
                        "frac_gt0": float("nan"),
                        "stat": float(row["stat"]),
                        "p": float(row["p"]),
                        "test": str(row["test"]),
                        "hit_p05": _hit(float(row["p"])),
                        "consensus": (
                            "median across 21 kpMS models"
                            if metric == "dr_object_prox"
                            else "none (original investigation export)"
                        ),
                        "mean_noSD": float(row["mean_noSD"]),
                        "mean_GHSD": float(row["mean_GHSD"]),
                        "mean_RBSD": float(row["mean_RBSD"]),
                        "median_noSD": float(row["median_noSD"]),
                        "median_GHSD": float(row["median_GHSD"]),
                        "median_RBSD": float(row["median_RBSD"]),
                    }
                )

    assoc_rows: list[dict[str, object]] = []
    for phase, g in animals.groupby("phase_layer", observed=True):
        for sex, gs in _sex_slices(g):
            for ycol, contrast in ASSOC_Y:
                rec = pearson_pair(gs["dr_original"].to_numpy(), gs[ycol].to_numpy())
                assoc_rows.append(
                    {
                        "phase_layer": str(phase),
                        "sex": sex,
                        "contrast": contrast,
                        "x": "dr_original",
                        "y": ycol,
                        "n": int(rec["n"]),
                        "pearson_r": float(rec["pearson_r"]),
                        "p": float(rec["p"]),
                        "hit_p05": _hit(float(rec["p"])),
                        "test": "pearson",
                        "y_source": "object-prox occupancy DR (median across 21 kpMS models)",
                    }
                )
    return animals, pd.DataFrame(test_rows), pd.DataFrame(assoc_rows)


def build_clock_tables(clocks: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Copy movement vs syllable clock metrics; Pearson within sex."""
    animals = clocks.copy()
    animals["animal_id"] = animals["animal_id"].astype(str)
    animals["phase_layer"] = pd.Categorical(animals["phase_layer"], categories=list(PHASES), ordered=True)
    animals = animals.sort_values(["phase_layer", "animal_id"]).reset_index(drop=True)

    assoc_rows: list[dict[str, object]] = []
    for phase, g in animals.groupby("phase_layer", observed=True):
        for sex, gs in _sex_slices(g):
            for xcol, ycol, contrast, family in CLOCK_PAIRS:
                rec = pearson_pair(gs[xcol].to_numpy(), gs[ycol].to_numpy())
                assoc_rows.append(
                    {
                        "phase_layer": str(phase),
                        "sex": sex,
                        "contrast": contrast,
                        "family": family,
                        "x": xcol,
                        "y": ycol,
                        "n": int(rec["n"]),
                        "pearson_r": float(rec["pearson_r"]),
                        "p": float(rec["p"]),
                        "hit_p05": _hit(float(rec["p"])),
                        "test": "pearson",
                        "note": (
                            "movement bout vs syllable bout clocks (different segmenters)"
                            if family == "two_clocks"
                            else "movement-bout aggregate vs session ambulation (same kinematics family)"
                        ),
                    }
                )
    return animals, pd.DataFrame(assoc_rows)


def build_presence_tables(deltas: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Consensus median-across-models Δ + one-sample t / Welch ANOVA within sex."""
    med = animal_median_across_models(deltas)
    med["phase_layer"] = pd.Categorical(med["phase_layer"], categories=list(PHASES), ordered=True)
    med["step"] = pd.Categorical(med["step"], categories=list(STEPS), ordered=True)
    med = med.sort_values(["phase_layer", "step", "animal_id"]).reset_index(drop=True)

    test_rows: list[dict[str, object]] = []
    for (phase, step), g in med.groupby(["phase_layer", "step"], observed=True):
        q = (
            "presence"
            if step == "no_obj->identical"
            else ("novelty" if step == "identical->novel" else "span")
        )
        for sex, gs in _sex_slices(g):
            grain = (
                "animal × phase × step (median across 21 models; txs pooled, within sex)"
                if sex != "all"
                else "animal × phase × step (median across 21 models; txs pooled, sexes pooled)"
            )
            for metric in PRESENCE_METRICS:
                rec = ttest_one_sample(gs[metric].to_numpy())
                test_rows.append(
                    {
                        "phase_layer": str(phase),
                        "step": str(step),
                        "question": q,
                        "metric": metric,
                        "grain": grain,
                        "sex": sex,
                        "hit_p05": _hit(float(rec["p"])),
                        "consensus": "median across 21 kpMS models",
                        **rec,
                    }
                )
        for metric in PRESENCE_METRICS:
            anova = anova_within_sex(g, metric=metric)
            for _, row in anova.iterrows():
                test_rows.append(
                    {
                        "phase_layer": str(phase),
                        "step": str(step),
                        "question": "tx_on_paired_delta",
                        "metric": metric,
                        "grain": "animal × phase × step (within sex)",
                        "sex": str(row["sex"]),
                        "n": int(row["n"]),
                        "mean_delta": float("nan"),
                        "median_delta": float("nan"),
                        "frac_gt0": float("nan"),
                        "stat": float(row["stat"]),
                        "p": float(row["p"]),
                        "test": str(row["test"]),
                        "hit_p05": _hit(float(row["p"])),
                        "consensus": "median across 21 kpMS models",
                        "mean_noSD": float(row["mean_noSD"]),
                        "mean_GHSD": float(row["mean_GHSD"]),
                        "mean_RBSD": float(row["mean_RBSD"]),
                        "median_noSD": float(row["median_noSD"]),
                        "median_GHSD": float(row["median_GHSD"]),
                        "median_RBSD": float(row["median_RBSD"]),
                    }
                )
    return med, pd.DataFrame(test_rows)


def write_info(out: Path) -> None:
    text = f"""# NOR protocol prologue (mean/interval cousins) — data dictionary

Protocol validation with **Student t / Welch ANOVA / Pearson only** — no
Wilcoxon, Kruskal, or Spearman. **Original** = first investigation-time analysis
(not a published survey standard). Object-prox and presence scalars use kpMS
bout clocks (median across 21 models). Ambulation speed/immobile is the original
displacement-hysteresis export — not syllable bouts.


|                 |                                                                                |
| --------------- | ------------------------------------------------------------------------------ |
| Generated       | 2026-08-21                                                                     |
| These files     | `{out.as_posix()}` |
| How regenerated | `OpenEthoMaze/scratch/nor_object_mi/simpler_first_protocol_prologue.py`        |


**Abbreviations**

- **NOR** — novel object recognition
- **DR** — discrimination ratio $(T_{{\\mathrm{{nvl}}}} - T_{{\\mathrm{{fam}}}}) / (T_{{\\mathrm{{nvl}}}} + T_{{\\mathrm{{fam}}}})$
- **tx** — treatment arm (`noSD`, `GHSD`, `RBSD`)
- **kpMS** — keypoint-MoSeq
- **t** — Student one-sample t (`ttest_1samp`) or paired t (`ttest_rel`)
- **Welch ANOVA** — Alexander–Govern equality of means (`welch_anova`)
- **Pearson** — Pearson $r$

**Question (plain):** Within each sex (txs pooled), does the NOR protocol change
near-locus engagement when objects appear, and does novel preference (DR) sit
above 0 — and is the novelty step (`identical→novel`) as strong as presence?

**Grain / consensus**

| Scalar | Grain | Consensus |
| ------ | ----- | --------- |
| `dr_original` | animal × phase × novel_obj | none (investigation export) |
| `dr_object_prox` | same | median across 21 kpMS models |
| presence/novelty `delta_*` | animal × phase × step | median across 21 kpMS models |
| `mean_speed_mps`, `time_immobile_s` | animal × phase × novel_obj | none (original ambulation export) |

**Association**

- Protocol preference / presence: one scalar vs 0 within sex → one-sample t
- Complementary: paired t of investigation seconds `t_nvl` vs `t_fam` (absolute time; not DR)
- Treatment coda: within sex → Welch ANOVA across tx
- Original DR vs object-prox / ambulation → Pearson within sex

**Hit rule (protocol):** `sex` in `{{F,M}}`, `test=ttest_1samp`, `p < 0.05` (txs pooled within sex). `sex=all` is companion only.

**Hit rule (tx coda):** within-sex `welch_anova`, `p < 0.05` (uncorrected).

**What this is not:** a tx-efficacy claim; syllable DA; MI; rank-test primary pack.

---

## Artifact map


| File | Unit of one row / figure | Notes |
| ---- | ------------------------ | ----- |
| `protocol_dr_per_animal.csv` | animal × phase | original + object-prox DR + ambulation + T_fam/T_nvl |
| `protocol_dr_tests_long.csv` | one t / paired-t / Welch ANOVA cell | preference + fam↔nvl seconds + tx |
| `protocol_dr_association.csv` | one Pearson cell | original vs object-prox DR within sex |
| `protocol_clock_metrics_per_animal.csv` | animal × phase | movement vs syllable clocks + session ambulation |
| `protocol_clock_association.csv` | one Pearson cell | two_clocks + move_litmus |
| `protocol_presence_deltas_per_animal.csv` | animal × phase × step | consensus median Δ |
| `protocol_presence_across_model_dispersion.csv` | animal × phase × step × metric | IQR/MAD salt (engagement primary) |
| `protocol_presence_across_model_dispersion_summary.csv` | phase × step × metric | cohort median of per-animal IQR |
| `protocol_presence_tests_long.csv` | one t or Welch ANOVA cell | presence / novelty / span / tx |
| `run_summary.json` | run metadata | 1 |
| `figures/fig_protocol_dr_association.{{pdf,svg}}` | original vs object-prox DR | Pearson within sex |
| `figures/fig_protocol_bout_clocks.{{pdf,svg}}` | movement vs syllable n/duration | Pearson within sex |
| `figures/fig_protocol_presence.{{pdf,svg}}` | presence engagement | one-sample t within sex |
| `figures/fig_protocol_novelty_step.{{pdf,svg}}` | novelty step | one-sample t within sex |
| `figures/fig_protocol_dr_preference.{{pdf,svg}}` | original + object-prox DR | one-sample t within sex |
| `figures/fig_protocol_tx_coda.{{pdf,svg}}` | Welch ANOVA by tx | hit/miss + p |
| `figures/FIGURES.md` | visual-encoding map | slides dest |


Upstream: `simpler_first_classic_dr/classic_dr_paired.csv`,
`simpler_first_presence_steps/presence_step_deltas_per_animal.csv`,
`simpler_first_ambulation_clocks/clock_metrics_per_animal.csv` (locked ss-50 syllable model).

**Clock caveat:** syllable NOR ladders have **count and duration only** — no bout
speed or immobile. Session `time_immobile_s` is ambulation-export only. Movement
bout speed/distance vs session totals is a same-family litmus, not a syllable
comparison.

---

## Regen

```powershell
uv run pytest scratch/nor_object_mi/test_simpler_first_protocol_prologue.py -q
uv run python scratch/nor_object_mi/simpler_first_protocol_prologue.py
uv run python scratch/nor_object_mi/fig_simpler_first_protocol_prologue.py --dest slides
```
"""
    (out / "INFO_protocol_prologue.md").write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--classic-paired", type=Path, default=DEFAULT_CLASSIC)
    ap.add_argument("--presence-deltas", type=Path, default=DEFAULT_PRESENCE)
    ap.add_argument("--presence-dispersion", type=Path, default=DEFAULT_DISPERSION)
    ap.add_argument(
        "--presence-dispersion-summary",
        type=Path,
        default=DEFAULT_DISPERSION_SUMMARY,
    )
    ap.add_argument("--clock-metrics", type=Path, default=DEFAULT_CLOCKS)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    paired = pd.read_csv(args.classic_paired)
    deltas = pd.read_csv(args.presence_deltas)
    clocks = pd.read_csv(args.clock_metrics)
    disp = pd.read_csv(args.presence_dispersion)
    disp_sum = pd.read_csv(args.presence_dispersion_summary)

    # Prologue figures only annotate engagement salt (commensurate across models).
    eng = disp["metric"].isin(("delta_frac_near", "delta_mean_dist_any_m"))
    disp_eng = disp.loc[eng].copy()
    disp_sum_eng = disp_sum[
        disp_sum["metric"].isin(("delta_frac_near", "delta_mean_dist_any_m"))
    ].copy()

    dr_animals, dr_tests, dr_assoc = build_dr_tables(paired)
    pr_animals, pr_tests = build_presence_tables(deltas)
    clock_animals, clock_assoc = build_clock_tables(clocks)

    dr_animals.to_csv(out / "protocol_dr_per_animal.csv", index=False)
    dr_tests.to_csv(out / "protocol_dr_tests_long.csv", index=False)
    dr_assoc.to_csv(out / "protocol_dr_association.csv", index=False)
    clock_animals.to_csv(out / "protocol_clock_metrics_per_animal.csv", index=False)
    clock_assoc.to_csv(out / "protocol_clock_association.csv", index=False)
    pr_animals.to_csv(out / "protocol_presence_deltas_per_animal.csv", index=False)
    pr_tests.to_csv(out / "protocol_presence_tests_long.csv", index=False)
    disp_eng.to_csv(out / "protocol_presence_across_model_dispersion.csv", index=False)
    disp_sum_eng.to_csv(
        out / "protocol_presence_across_model_dispersion_summary.csv", index=False
    )

    t_pref = dr_tests[
        (dr_tests["test"] == "ttest_1samp")
        & (dr_tests["sex"].isin(list(SEX_ORDER)))
        & (dr_tests["metric"] == "dr_original")
    ]
    t_pres = pr_tests[
        (pr_tests["test"] == "ttest_1samp")
        & (pr_tests["sex"].isin(list(SEX_ORDER)))
        & (pr_tests["step"] == "no_obj->identical")
        & (pr_tests["metric"] == "delta_frac_near")
    ]
    t_nov = pr_tests[
        (pr_tests["test"] == "ttest_1samp")
        & (pr_tests["sex"].isin(list(SEX_ORDER)))
        & (pr_tests["step"] == "identical->novel")
        & (pr_tests["metric"] == "delta_frac_near")
    ]
    summary = {
        "stage": "protocol_prologue_mean_interval",
        "tests": ["ttest_1samp", "ttest_rel", "welch_anova", "pearson"],
        "protocol_sex": list(SEX_ORDER),
        "n_dr_animals": int(len(dr_animals)),
        "n_presence_animals_rows": int(len(pr_animals)),
        "n_clock_animals": int(len(clock_animals)),
        "n_dr_test_rows": int(len(dr_tests)),
        "n_presence_test_rows": int(len(pr_tests)),
        "n_assoc_rows": int(len(dr_assoc)),
        "n_clock_assoc_rows": int(len(clock_assoc)),
        "dr_original_ttest_hits_FM": int(t_pref["hit_p05"].sum()),
        "presence_frac_near_ttest_hits_FM": int(t_pres["hit_p05"].sum()),
        "novelty_frac_near_ttest_hits_FM": int(t_nov["hit_p05"].sum()),
        "inputs": {
            "classic_paired": str(args.classic_paired),
            "presence_deltas": str(args.presence_deltas),
            "presence_dispersion": str(args.presence_dispersion),
            "clock_metrics": str(args.clock_metrics),
        },
        "path": str(out),
        "syllable_clock_note": "NOR ladders: syllable count/duration only; no bout speed/immobile",
    }
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_info(out)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
