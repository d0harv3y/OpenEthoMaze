"""DR-framed deck boards A/C/D/E/F for exemplar raw alphabet.

Exemplar: paramscan_s1-1e7_s2-3e4_ss-100. Not cluster_id panels.
Ticket: .scratch/dr-framed-motion-seq-deck/issues/07-build-join-boards.md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    CONDITION_COLOR,
    CONDITION_ORDER,
    SEX_MARKER,
    SEX_ORDER,
    condition_sex_legend_handles,
    fig_footnote,
)
from nor_object_mi.fig_prox_quad_comp_violins import (  # noqa: E402
    _long_from_wide,
    run_board,
)
from nor_object_mi.fig_prox_quad_session_step_comp_violins import (  # noqa: E402
    _paired_delta_long,
    run_board as run_session_board,
)
from nor_object_mi.prox_comp import (  # noqa: E402
    PER_SCALAR_FAMILY_METRICS,
    PER_SCALAR_FAMILY_NAME,
    assert_per_scalar_family_sizes,
)
from nor_object_mi.simpler_first_da import apply_bh_grouped  # noqa: E402
from nor_object_mi.simpler_first_prox_quad_per_model import run as run_per_model  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402

EXEMPLAR = "paramscan_s1-1e7_s2-3e4_ss-100"
PAUSE_SYLL = 5
DEFAULT_NOR = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_ENSEMBLE = Path(r"D:\sack\datas\impress\moseq_251017")
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_dr_framed_deck_exemplar"
)
CLASSIC_CSV = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_classic_dr\classic_dr_per_animal.csv"
)
FRAC_STILL_CSV = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\slides_pack\frac_still\frac_still_animal.csv"
)
SYLL_SHARE_CSV = Path(
    r"D:\sack\crosscorr\out_spearman_moseq_physio\moseq_251017"
    rf"\{EXEMPLAR}\tables\syllable_frame_share_long.csv"
)
def _spearman(x: np.ndarray, y: np.ndarray) -> dict[str, float | bool | int]:
    ok = np.isfinite(x) & np.isfinite(y)
    n = int(ok.sum())
    if n < 3:
        return {"n": n, "spearman_rho": float("nan"), "p": float("nan"), "hit_p05": False}
    rho, p = stats.spearmanr(x[ok], y[ok])
    return {
        "n": n,
        "spearman_rho": float(rho),
        "p": float(p),
        "hit_p05": bool(np.isfinite(p) and float(p) < 0.05),
    }


def _scatter_one(
    df: pd.DataFrame,
    *,
    xcol: str,
    ycol: str,
    out: Path,
    title: str,
    xlabel: str,
    ylabel: str,
    style_condition_sex: bool = False,
    footnote: str | None = None,
) -> Path:
    """Scatter; optional violin-board markers (color=condition, shape=sex)."""
    fig, ax = plt.subplots(figsize=(5.5, 5.2), layout="constrained")
    x = pd.to_numeric(df[xcol], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(df[ycol], errors="coerce").to_numpy(dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    if style_condition_sex and {"condition", "sex"}.issubset(df.columns):
        cond = df["condition"].astype(str).to_numpy()
        sex = df["sex"].astype(str).to_numpy()
        for t in CONDITION_ORDER:
            for s in SEX_ORDER:
                m = ok & (cond == t) & (sex == s)
                if not np.any(m):
                    continue
                ax.scatter(
                    x[m],
                    y[m],
                    c=CONDITION_COLOR[t],
                    marker=SEX_MARKER[s],
                    s=36,
                    alpha=0.85,
                    linewidths=0.3,
                    edgecolors="white",
                    zorder=3,
                )
        ax.legend(
            handles=condition_sex_legend_handles(dest="slides"),
            loc="lower right",
            frameon=False,
            fontsize=9,
            ncol=1,
        )
    else:
        ax.scatter(x[ok], y[ok], s=28, alpha=0.75, edgecolors="none", c="#333333")
    if ok.sum() >= 2:
        lo = float(min(np.nanmin(x[ok]), np.nanmin(y[ok])))
        hi = float(max(np.nanmax(x[ok]), np.nanmax(y[ok])))
        pad = 0.05 * (hi - lo + 1e-9)
        ax.plot([lo - pad, hi + pad], [lo - pad, hi + pad], ls="--", color="#bbbbbb", lw=0.9)
    sp = _spearman(x, y)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.text(
        0.02,
        0.98,
        f"rho={sp['spearman_rho']:.3f}  p={sp['p']:.3g}  n={sp['n']}",
        transform=ax.transAxes,
        va="top",
        fontsize=9,
        family="monospace",
    )
    if footnote:
        fig_footnote(fig, footnote, fontsize=8, y=-0.08)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=160, bbox_inches="tight")
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    return out.with_suffix(".png")


def ensure_exemplar_scores(
    *,
    nor_h5: Path,
    ensemble: Path,
    out_dir: Path,
    min_frames: int,
) -> Path:
    """Score exemplar only; write per_model_per_animal.csv under out_dir/scores."""
    score_dir = out_dir / "scores"
    csv = score_dir / "per_model_per_animal.csv"
    if csv.is_file():
        df = pd.read_csv(csv)
        if "dr_time_prox" in df.columns and "dr_hill2_prox" in df.columns:
            print(f"reuse scores {csv}", flush=True)
            return csv
    print(f"scoring {EXEMPLAR} min_frames={min_frames}", flush=True)
    run_per_model(
        nor_h5,
        ensemble,
        score_dir,
        min_frames=min_frames,
        models=[EXEMPLAR],
    )
    return csv


def board_a_d(classic: pd.DataFrame, prox: pd.DataFrame, out: Path) -> pd.DataFrame:
    """Join classic DR to time + composition DR cousins @ NOR_TX."""
    c = classic[classic["session"] == "NOR_TX"].copy()
    p = prox[(prox["session"] == "NOR_TX") & (prox["model"] == EXEMPLAR)].copy()
    c["animal_id"] = c["animal_id"].astype(str)
    p["animal_id"] = p["animal_id"].astype(str)
    keys = ["animal_id", "sex", "condition", "session"]
    m = c.merge(p, on=keys, how="inner", suffixes=("", "_prox"))
    ycols = ["dr_time_prox", "dr_shannon_prox", "dr_richness_prox", "dr_hill2_prox"]
    rows: list[dict[str, object]] = []
    fig_dir = out / "figures"
    for y in ycols:
        elig = (
            m["time_contrast_eligible"].astype(bool)
            if y == "dr_time_prox"
            else m["contrast_eligible_prox"].astype(bool)
        )
        sub = m.loc[elig].copy()
        sp = _spearman(
            pd.to_numeric(sub["dr_classic"], errors="coerce").to_numpy(dtype=float),
            pd.to_numeric(sub[y], errors="coerce").to_numpy(dtype=float),
        )
        rows.append({"board": "A" if y == "dr_time_prox" else "D", "x": "dr_classic", "y": y, **sp})
        _scatter_one(
            sub,
            xcol="dr_classic",
            ycol=y,
            out=fig_dir / f"fig_classic_vs_{y}_NOR_TX",
            title=f"classic DR vs {y}  ·  NOR_TX  ·  {EXEMPLAR}",
            xlabel="classic investigation DR",
            ylabel=y,
            style_condition_sex=True,
        )
    assoc = pd.DataFrame(rows)
    assoc.to_csv(out / "classic_vs_prox_assoc_NOR_TX.csv", index=False)
    m.to_csv(out / "classic_vs_prox_joined_NOR_TX.csv", index=False)
    return assoc


def board_c(frac: pd.DataFrame, share: pd.DataFrame, out: Path) -> pd.DataFrame:
    s = share[share["syllable"].astype(int) == PAUSE_SYLL].copy()
    s = s.rename(columns={"ID": "animal_id", "TX": "condition", "share": "syll5_frame_share"})
    frac = frac.copy()
    frac["animal_id"] = frac["animal_id"].astype(str)
    s["animal_id"] = s["animal_id"].astype(str)
    keys = ["animal_id", "sex", "condition", "session", "trial"]
    m = frac.merge(s[keys + ["syll5_frame_share"]], on=keys, how="inner")
    m = m.rename(columns={"p": "frac_still"})
    rows: list[dict[str, object]] = []
    # full ladder + recognition-only inset stats
    for label, sub in (
        ("all_ladder", m),
        ("NOR_TX_nvl_obj", m[(m["session"] == "NOR_TX") & (m["trial"] == "nvl_obj")]),
    ):
        sp = _spearman(
            pd.to_numeric(sub["frac_still"], errors="coerce").to_numpy(dtype=float),
            pd.to_numeric(sub["syll5_frame_share"], errors="coerce").to_numpy(dtype=float),
        )
        rows.append({"board": "C", "grain": label, "x": "frac_still", "y": "syll5_frame_share", **sp})
    assoc = pd.DataFrame(rows)
    assoc.to_csv(out / "still_vs_syll5_assoc.csv", index=False)
    m.to_csv(out / "still_vs_syll5_joined.csv", index=False)
    _scatter_one(
        m,
        xcol="frac_still",
        ycol="syll5_frame_share",
        out=out / "figures" / "fig_frac_still_vs_syll5_share",
        title=f"frac_still vs pause syll{PAUSE_SYLL} share  ·  {EXEMPLAR}",
        xlabel="frac_still",
        ylabel=f"syll{PAUSE_SYLL} frame share",
        style_condition_sex=True,
        footnote=(
            "frac_still = time_immobile_s / duration_s (IMPRESS ambulation, fore "
            "displacement hysteresis). Defaults: start sqrt(2)/150 m/frame, stop "
            "sqrt(2)/300 m/frame, median window 3, entry/exit debounce 3 frames, "
            f"min bout 4 frames. Y = raw syll{PAUSE_SYLL} frame share on exemplar. "
            "Grain: animal x session x trial. Color=tx, shape=sex."
        ),
    )
    return assoc


def board_e_f(prox: pd.DataFrame, out: Path) -> None:
    """Exemplar ProxComp violins + session-step boards (prox only)."""
    df = prox[prox["model"] == EXEMPLAR].copy()
    df["contrast_eligible"] = df["contrast_eligible_prox"].astype(bool)
    e_dir = out / "comp_level"
    f_dir = out / "session_step"
    e_dir.mkdir(parents=True, exist_ok=True)
    f_dir.mkdir(parents=True, exist_ok=True)
    (e_dir / "figures").mkdir(exist_ok=True)
    (f_dir / "figures").mkdir(exist_ok=True)

    # Per-scalar condition BH @ NOR_TX
    sub = df[(df["session"] == "NOR_TX") & df["contrast_eligible"]].copy()
    parts = []
    for metric in PER_SCALAR_FAMILY_METRICS:
        k = kruskal_within_sex(sub, metric=metric).copy()
        k["family"] = PER_SCALAR_FAMILY_NAME[metric]
        k["metric"] = metric
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(("F", "M"))].reset_index(drop=True)
    counts = {
        m: int(pd.to_numeric(tests.loc[tests["metric"] == m, "p"], errors="coerce").notna().sum())
        for m in PER_SCALAR_FAMILY_METRICS
    }
    assert_per_scalar_family_sizes(counts)
    # Deck FDR: sex-stratified per-scalar (m=1 within sex×metric). Sealed vault
    # contract remains BH within metric across F+M (m=2); both written below.
    tests_sealed = apply_bh_grouped(tests.copy(), ["metric"])
    tests_sealed.to_csv(e_dir / "exemplar_prox_per_scalar_tests_sealed_m2.csv", index=False)
    tests = apply_bh_grouped(tests, ["sex", "metric"])
    tests.to_csv(e_dir / "exemplar_prox_per_scalar_tests.csv", index=False)
    tests.to_csv(e_dir / "exemplar_prox_per_scalar_tests_sex_strat.csv", index=False)

    alphabet = f"raw:{EXEMPLAR}"
    bh_sex: tuple[str, ...] = ("sex",)
    for kind in ("shannon", "richness", "hill2"):
        print(f"=== E prox {kind} (sex-strat BH) ===", flush=True)
        long = _long_from_wide(
            df, roi="prox", kind=kind, elig_col="contrast_eligible", alphabet=alphabet
        )
        run_board(
            long=long,
            out=e_dir,
            dest="slides",
            roi="prox",
            kind=kind,
            tag="exemplar",
            alphabet=alphabet,
            salted=False,
            bh_group_cols=bh_sex,
        )
        print(f"=== F session-step prox {kind} (sex-strat BH) ===", flush=True)
        delta_long = _paired_delta_long(
            df,
            roi="prox",
            kind=kind,
            elig_col="contrast_eligible_prox",
            alphabet=alphabet,
            model_col=None,
        )
        run_session_board(
            long=delta_long,
            out=f_dir,
            dest="slides",
            roi="prox",
            kind=kind,
            tag="exemplar",
            alphabet=alphabet,
            salted=False,
            bh_group_cols=bh_sex,
        )


def write_info(out: Path, summary: dict[str, object]) -> None:
    text = f"""# INFO — DR-framed deck exemplar boards

Exemplar model `{EXEMPLAR}` (raw_syllable_id). Pause syllable = {PAUSE_SYLL}.

## Boards

| ID | Claim |
|----|-------|
| A | classic DR ↔ dr_time_prox @ NOR_TX |
| C | frac_still ↔ syll{PAUSE_SYLL} frame-share (ladder) |
| D | classic DR ↔ dr_shannon/richness/hill2_prox @ NOR_TX |
| E | ProxComp level/DR violins + per-scalar Kruskal (exemplar) |
| F | Session-step prox composition (exemplar) |

Reuse elsewhere: classic↔object-prox (`fig_classic_vs_object_prox`); session_paired time twin.

## Regen

```powershell
uv run python scratch/nor_object_mi/simpler_first_dr_framed_deck_boards.py
```

## Summary

```json
{json.dumps(summary, indent=2)}
```
"""
    (out / "INFO_dr_framed_deck_exemplar.md").write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR)
    ap.add_argument("--ensemble-root", type=Path, default=DEFAULT_ENSEMBLE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--classic-csv", type=Path, default=CLASSIC_CSV)
    ap.add_argument("--frac-still-csv", type=Path, default=FRAC_STILL_CSV)
    ap.add_argument("--syll-share-csv", type=Path, default=SYLL_SHARE_CSV)
    ap.add_argument("--min-frames", type=int, default=10)
    ap.add_argument("--skip-score", action="store_true")
    args = ap.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    if args.skip_score:
        score_csv = out / "scores" / "per_model_per_animal.csv"
        if not score_csv.is_file():
            raise FileNotFoundError(score_csv)
    else:
        score_csv = ensure_exemplar_scores(
            nor_h5=args.nor_h5,
            ensemble=args.ensemble_root,
            out_dir=out,
            min_frames=args.min_frames,
        )
    prox = pd.read_csv(score_csv)
    classic = pd.read_csv(args.classic_csv)
    frac = pd.read_csv(args.frac_still_csv)
    share = pd.read_csv(args.syll_share_csv)

    print("=== boards A/D ===", flush=True)
    assoc_ad = board_a_d(classic, prox, out)
    print("=== board C ===", flush=True)
    assoc_c = board_c(frac, share, out)
    print("=== boards E/F ===", flush=True)
    board_e_f(prox, out)

    summary = {
        "status": "ok",
        "exemplar": EXEMPLAR,
        "pause_syllable": PAUSE_SYLL,
        "min_frames_n": int(args.min_frames),
        "assoc_AD": assoc_ad.to_dict(orient="records"),
        "assoc_C": assoc_c.to_dict(orient="records"),
        "elapsed_s": float(time.time() - t0),
    }
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_info(out, summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
