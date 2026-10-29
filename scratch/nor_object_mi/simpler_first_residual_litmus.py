"""Family Residual-A — syllable scores residualized on Layer A covariates.

Join locked Y (Shannon, H(next|current), pair MI) and X (speed, frac_still,
frac_near_nvl) at NOR_TX x nvl_obj. OLS residualize within sex; Kruskal residual
by condition within sex; BH FDR over the pre-declared 6-cell Residual-A family.

Contract: docs/vaults/openethomaze/families/F Residual-A.md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.residual_litmus import (  # noqa: E402
    FAMILY_A_SIZE,
    FAMILY_SESSION,
    FAMILY_SEXES,
    FAMILY_TRIAL,
    GRAIN,
    RAW_Y_METRICS,
    RESID_METRICS,
    X_COVARIATES,
    assert_family_a_size,
    residualize_within_sex,
)
from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402

_ROOT = Path(r"D:\sack\datas\impress\moseq_251017\_nor_object_mi")
DEFAULT_SHANNON = _ROOT / "slides_pack" / "shannon" / "shannon_animal_level.csv"
DEFAULT_STILL = _ROOT / "slides_pack" / "frac_still" / "frac_still_animal.csv"
DEFAULT_H = _ROOT / "simpler_first_transition_structure" / "transition_structure_per_animal.csv"
DEFAULT_MI = _ROOT / "simpler_first_ngram_seq" / "ngram_seq_per_animal.csv"
DEFAULT_PROX = _ROOT / "simpler_first_object_prox_0p10" / "object_prox_metrics_per_animal.csv"
DEFAULT_SPEED = _ROOT / "simpler_first_protocol_prologue" / "protocol_dr_per_animal.csv"
DEFAULT_OUT = _ROOT / "simpler_first_residual_litmus"


def _aid(s: pd.Series) -> pd.Series:
    return s.astype(str)


def _grain_filter(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["animal_id"] = _aid(out["animal_id"])
    if "session" in out.columns:
        out = out[out["session"].astype(str) == FAMILY_SESSION]
    if "trial" in out.columns:
        out = out[out["trial"].astype(str) == FAMILY_TRIAL]
    return out.reset_index(drop=True)


def load_joined(
    *,
    shannon_csv: Path,
    still_csv: Path,
    h_csv: Path,
    mi_csv: Path,
    prox_csv: Path,
    speed_csv: Path,
) -> pd.DataFrame:
    h = _grain_filter(pd.read_csv(h_csv))
    mi = _grain_filter(pd.read_csv(mi_csv))
    shan = _grain_filter(pd.read_csv(shannon_csv)).rename(columns={"p": "shannon_bits"})
    still = _grain_filter(pd.read_csv(still_csv)).rename(columns={"p": "frac_still"})

    speed = pd.read_csv(speed_csv)
    speed["animal_id"] = _aid(speed["animal_id"])
    speed = speed[speed["session"].astype(str) == FAMILY_SESSION][
        ["animal_id", "mean_speed_mps"]
    ].drop_duplicates("animal_id")

    prox = pd.read_csv(prox_csv)
    prox["animal_id"] = _aid(prox["animal_id"])
    prox = prox[prox["session"].astype(str) == FAMILY_SESSION]
    prox_med = (
        prox.groupby("animal_id", as_index=False)["frac_near_nvl"]
        .median()
        .rename(columns={"frac_near_nvl": "frac_near_nvl"})
    )

    base = h[
        [
            "animal_id",
            "sex",
            "condition",
            "session",
            "trial",
            "H_next_given_curr",
        ]
    ].copy()
    base = base.merge(mi[["animal_id", "pair_MI"]], on="animal_id", how="inner")
    base = base.merge(shan[["animal_id", "shannon_bits"]], on="animal_id", how="inner")
    base = base.merge(still[["animal_id", "frac_still"]], on="animal_id", how="inner")
    base = base.merge(speed, on="animal_id", how="inner")
    base = base.merge(prox_med, on="animal_id", how="inner")

    need = list(RAW_Y_METRICS) + list(X_COVARIATES)
    before = len(base)
    base = base.dropna(subset=need).reset_index(drop=True)
    base.attrs["n_drop_incomplete"] = int(before - len(base))
    return base


def run(
    *,
    shannon_csv: Path,
    still_csv: Path,
    h_csv: Path,
    mi_csv: Path,
    prox_csv: Path,
    speed_csv: Path,
    out_dir: Path,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    animals = load_joined(
        shannon_csv=shannon_csv,
        still_csv=still_csv,
        h_csv=h_csv,
        mi_csv=mi_csv,
        prox_csv=prox_csv,
        speed_csv=speed_csv,
    )
    n_drop = int(animals.attrs.get("n_drop_incomplete", 0))
    animals, coef = residualize_within_sex(animals)
    animals.to_csv(out_dir / "residual_litmus_per_animal.csv", index=False)
    coef.to_csv(out_dir / "residual_litmus_ols_coef.csv", index=False)

    parts: list[pd.DataFrame] = []
    for metric in RESID_METRICS:
        k = kruskal_within_sex(animals, metric=metric)
        k = k.copy()
        k["session"] = FAMILY_SESSION
        k["trial"] = FAMILY_TRIAL
        k["grain"] = GRAIN
        k["family"] = "Residual-A"
        k["question"] = "q5_residual_litmus_condition"
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    n_finite = int(pd.to_numeric(tests["p"], errors="coerce").notna().sum())
    assert_family_a_size(n_finite)
    tests = apply_bh(tests)
    tests.to_csv(out_dir / "residual_litmus_tests_long.csv", index=False)

    # Descriptive companion only — raw Y Kruskal, NOT in Residual-A BH family.
    raw_parts: list[pd.DataFrame] = []
    for metric in RAW_Y_METRICS:
        k = kruskal_within_sex(animals, metric=metric)
        k = k.copy()
        k["session"] = FAMILY_SESSION
        k["trial"] = FAMILY_TRIAL
        k["grain"] = GRAIN
        k["family"] = "Residual-A-raw-companion"
        k["question"] = "q5_residual_litmus_raw_descriptive"
        raw_parts.append(k)
    raw_tests = pd.concat(raw_parts, ignore_index=True)
    raw_tests = raw_tests[raw_tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    raw_tests = apply_bh(raw_tests)
    raw_tests.to_csv(out_dir / "residual_litmus_raw_companion_tests.csv", index=False)

    n_hit = int(tests["hit_fdr05"].astype(bool).sum())
    n_p05 = int(tests["hit_p05"].astype(bool).sum())
    summary: dict[str, object] = {
        "status": "ok",
        "family": "Residual-A",
        "family_size": FAMILY_A_SIZE,
        "residualizer": "OLS within sex: Y ~ mean_speed_mps + frac_still + frac_near_nvl",
        "y_metrics": list(RAW_Y_METRICS),
        "resid_metrics": list(RESID_METRICS),
        "x_covariates": list(X_COVARIATES),
        "n_animals": int(animals["animal_id"].nunique()),
        "n_drop_incomplete": n_drop,
        "n_hit_fdr05": n_hit,
        "n_hit_p05": n_p05,
        "pass_family_a": bool(n_hit > 0),
        "sexes": list(FAMILY_SEXES),
        "session": FAMILY_SESSION,
        "trial": FAMILY_TRIAL,
        "grain": GRAIN,
        "sources": {
            "shannon": str(shannon_csv),
            "frac_still": str(still_csv),
            "H_next_given_curr": str(h_csv),
            "pair_MI": str(mi_csv),
            "frac_near_nvl": str(prox_csv) + " (median across models @ NOR_TX)",
            "mean_speed_mps": str(speed_csv) + " (session NOR_TX)",
        },
        "hit_rule": "q_bh < 0.05 within Residual-A (6 Kruskal cells)",
        "elapsed_s": float(time.time() - t0),
    }
    if n_hit > 0:
        hits = tests.loc[tests["hit_fdr05"].astype(bool)].copy()
        summary["hits"] = hits[
            ["sex", "metric", "p", "q_bh", "n", "median_noSD", "median_GHSD", "median_RBSD"]
        ].to_dict(orient="records")
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "n_animals",
                    "n_drop_incomplete",
                    "n_hit_fdr05",
                    "n_hit_p05",
                    "pass_family_a",
                    "family_size",
                )
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def write_info_md(out_dir: Path, summary: dict[str, object]) -> None:
    text = f"""# Residual litmus (syllable Y ⊥ Layer A) — data dictionary

Per-animal **OLS residuals** of locked syllable scalars after regressing out
Layer A covariates (speed / immobile / near-novel occupancy) at `NOR_TX` x
`nvl_obj`. Independent-groups Kruskal by `condition` within sex; Benjamini–Hochberg
(**BH**) false-discovery rate (**FDR**) over pre-declared **Residual-A** (6 cells).

This is a **redundancy litmus**, not a new MoSeq miracle hunt. It asks whether
any leftover of Shannon / H(next|current) / pair MI still separates condition
after removing the movement / proximity clock.

| | |
|---|---|
| Generated | 2026-10-05 |
| These files | `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_residual_litmus/` |
| This run | Family Residual-A (3 residuals x F/M); OLS within sex |
| How regenerated | `OpenEthoMaze/scratch/nor_object_mi/simpler_first_residual_litmus.py` (lib `residual_litmus.py`; litmus `test_residual_litmus.py`) |

**Abbreviations**

- **NOR** — novel object recognition
- **BH / FDR** — Benjamini–Hochberg / false-discovery rate
- **OLS** — ordinary least squares
- **MI** — mutual information
- **kpMS** — keypoint-MoSeq (upstream of H / pair MI only)
- **Kruskal** — Kruskal–Wallis

**Question (plain):** After residualizing declared syllable scores on speed,
`frac_still`, and `frac_near_nvl`, does `condition` still separate the residuals?

**Grain:** `animal x NOR_TX x nvl_obj`.

---

## Residualizer (locked)

Within sex:

```
Y ~ intercept + mean_speed_mps + frac_still + frac_near_nvl
resid = Y - Yhat
```

| Token | Role | Source |
|---|---|---|
| `shannon_bits` | Y | `slides_pack/shannon/shannon_animal_level.csv` (`p`) |
| `H_next_given_curr` | Y | `simpler_first_transition_structure/transition_structure_per_animal.csv` |
| `pair_MI` | Y | `simpler_first_ngram_seq/ngram_seq_per_animal.csv` |
| `mean_speed_mps` | X | `simpler_first_protocol_prologue/protocol_dr_per_animal.csv` @ `NOR_TX` (session locomotor clock) |
| `frac_still` | X | `slides_pack/frac_still/frac_still_animal.csv` (`p`) @ grain |
| `frac_near_nvl` | X | median across models from `object_prox_metrics_per_animal.csv` @ `NOR_TX` |

Incomplete rows (any Y/X missing) are dropped. This run: n_animals={summary.get("n_animals")}, n_drop_incomplete={summary.get("n_drop_incomplete")}.

| Association | Test | Hit rule |
|---|---|---|
| Independent groups (`condition`) within sex on **residuals** | Kruskal | `hit_fdr05` <=> `q_bh < 0.05` within Residual-A (6) |

**D vs I:** per-animal CSV = **D** until Kruskal + BH; tests = **I**.

Raw-Y Kruskal lives in `residual_litmus_raw_companion_tests.csv` as **descriptive companion only** (separate BH table; not Family A).

---

## Artifact map

| File | Unit of one row |
|---|---|
| `residual_litmus_per_animal.csv` | animal (raw Y, X, resid_*) |
| `residual_litmus_ols_coef.csv` | sex x Y regression coefs |
| `residual_litmus_tests_long.csv` | Family A Kruskal cell |
| `residual_litmus_raw_companion_tests.csv` | descriptive raw-Y cells |
| `run_summary.json` | knobs + pass/fail |

---

## Shared keys

| Field | Allowed / meaning |
|---|---|
| `animal_id` | cohort animal |
| `sex` | `F`, `M` |
| `condition` | `noSD`, `GHSD`, `RBSD` |
| `session` / `trial` | `NOR_TX` / `nvl_obj` |
| `metric` (tests) | `resid_shannon_bits`, `resid_H_next_given_curr`, `resid_pair_MI` |

---

## Run summary (this execution)

```json
{json.dumps({k: summary[k] for k in summary if k != "sources"}, indent=2)}
```

Contract: `docs/vaults/openethomaze/families/F Residual-A.md`.
"""
    (out_dir / "INFO_residual_litmus.md").write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shannon-csv", type=Path, default=DEFAULT_SHANNON)
    ap.add_argument("--still-csv", type=Path, default=DEFAULT_STILL)
    ap.add_argument("--h-csv", type=Path, default=DEFAULT_H)
    ap.add_argument("--mi-csv", type=Path, default=DEFAULT_MI)
    ap.add_argument("--prox-csv", type=Path, default=DEFAULT_PROX)
    ap.add_argument("--speed-csv", type=Path, default=DEFAULT_SPEED)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    for label, p in (
        ("shannon", args.shannon_csv),
        ("still", args.still_csv),
        ("h", args.h_csv),
        ("mi", args.mi_csv),
        ("prox", args.prox_csv),
        ("speed", args.speed_csv),
    ):
        if not p.is_file():
            print(f"{label} missing: {p}", file=sys.stderr)
            return 1
    summary = run(
        shannon_csv=args.shannon_csv,
        still_csv=args.still_csv,
        h_csv=args.h_csv,
        mi_csv=args.mi_csv,
        prox_csv=args.prox_csv,
        speed_csv=args.speed_csv,
        out_dir=args.out_dir,
    )
    write_info_md(args.out_dir, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
