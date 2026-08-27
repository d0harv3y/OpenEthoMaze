"""Q2: syllable composition in the locked novel_obj window (COUNT / UNCERTAINTY / DIFFERENCE).

Grain: animal × NOR_TX × novel_obj; pool bout frames by raw_syllable_id.
PERMANOVA is analogy-only (syllable domain + this grain). No CLR / PCoA / UniFrac.
skbio is not in the env; permutation PERMANOVA uses SciPy Bray–Curtis + Anderson 2001.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_q1 import (
    LOCKED,
    SEX_ORDER,
    TX_COLORS,
    TX_ORDER,
    kruskal_within_sex,
)

N_PERM = 999
PERM_SEED = 42


def shannon_bits(p: np.ndarray) -> float:
    """Abundance uncertainty H = −∑ p log2 p over p > 0 (bits)."""
    q = np.asarray(p, dtype=np.float64)
    q = q[np.isfinite(q) & (q > 0)]
    if q.size == 0:
        return float("nan")
    q = q / q.sum()
    return float(-np.sum(q * np.log2(q)))


def compositions_from_bouts(
    bouts: pd.DataFrame,
    *,
    phase_layer: str | None = None,
    condition_layer: str | None = None,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Return (animal table, P n×K frame-share matrix, syllable ids)."""
    phase = phase_layer or str(LOCKED["phase_layer"])
    cond = condition_layer or str(LOCKED["condition_layer"])
    sub = bouts[(bouts["phase_layer"] == phase) & (bouts["condition_layer"] == cond)].copy()
    if sub.empty:
        raise ValueError(f"no {cond} bouts for phase {phase}")
    syll_ids = np.sort(sub["raw_syllable_id"].astype(np.int64).unique())
    animals = []
    rows = []
    for aid, g in sub.groupby("animal_id", sort=True):
        counts = g.groupby("raw_syllable_id")["bout_frames"].sum()
        vec = np.array([float(counts.get(s, 0.0)) for s in syll_ids], dtype=np.float64)
        tot = float(vec.sum())
        p = vec / tot if tot > 0 else vec
        richness = int(np.sum(vec > 0))
        animals.append(
            {
                "animal_id": str(aid),
                "sex": str(g["sex"].iloc[0]),
                "tx": str(g["tx"].iloc[0]),
                "phase_layer": phase,
                "n_frames": int(tot),
                "richness": richness,
                "shannon_bits": shannon_bits(p),
            }
        )
        rows.append(p)
    meta = pd.DataFrame(animals)
    P = np.vstack(rows)
    return meta, P, syll_ids


def _ss_from_d2(d2: np.ndarray, n: int) -> float:
    """SS = (1/n) ∑_{i<j} d_ij^2 from a square matrix of squared distances."""
    iu = np.triu_indices(n, k=1)
    return float(d2[iu].sum() / n)


def permanova_pseudo_f(d2: np.ndarray, groups: np.ndarray) -> float:
    """Anderson (2001) pseudo-F on squared distances."""
    n = int(d2.shape[0])
    labels, counts = np.unique(groups, return_counts=True)
    a = int(labels.size)
    if a < 2 or n <= a:
        return float("nan")
    ss_t = _ss_from_d2(d2, n)
    ss_w = 0.0
    for lab, nk in zip(labels, counts):
        idx = np.flatnonzero(groups == lab)
        if nk < 2:
            return float("nan")
        ss_w += _ss_from_d2(d2[np.ix_(idx, idx)], int(nk))
        ss_a = ss_t - ss_w
        if ss_w == 0.0:
            return float("inf") if ss_a > 0 else float("nan")
        return float((ss_a / (a - 1)) / (ss_w / (n - a)))


def permanova_braycurtis(
    P: np.ndarray,
    groups: np.ndarray,
    *,
    n_perm: int = N_PERM,
    seed: int = PERM_SEED,
) -> dict[str, object]:
    """Permutation PERMANOVA; DIFFERENCE = Bray–Curtis (analogy-only on syllables)."""
    n = int(P.shape[0])
    if n < 4:
        return {"test": "permanova", "distance": "braycurtis", "F": float("nan"), "p": float("nan"), "n": n, "n_perm": 0}
    d = squareform(pdist(P, metric="braycurtis"))
    d2 = d * d
    f_obs = permanova_pseudo_f(d2, groups)
    rng = np.random.default_rng(seed)
    n_ge = 0
    for _ in range(int(n_perm)):
        perm = rng.permutation(groups)
        f_p = permanova_pseudo_f(d2, perm)
        if np.isfinite(f_obs) and f_obs == float("inf"):
            n_ge += int(np.isfinite(f_p) and f_p == float("inf"))
        elif np.isfinite(f_p) and np.isfinite(f_obs) and f_p >= f_obs:
            n_ge += 1
    p = (n_ge + 1) / (int(n_perm) + 1)
    return {
        "test": "permanova",
        "distance": "braycurtis",
        "operation": "DIFFERENCE+TEST",
        "domain": "syllable",
        "analogy_only": True,
        "F": f_obs,
        "p": float(p),
        "n": n,
        "n_perm": int(n_perm),
        "seed": int(seed),
        "n_ge_obs": int(n_ge),
    }


def permanova_within_sex(meta: pd.DataFrame, P: np.ndarray) -> pd.DataFrame:
    rows = []
    for sex in SEX_ORDER:
        mask = (meta["sex"].to_numpy() == sex)
        sub_p = P[mask]
        groups = meta.loc[mask, "tx"].to_numpy()
        rec = permanova_braycurtis(sub_p, groups)
        rec["sex"] = sex
        rec["metric"] = "braycurtis_composition"
        for tx in TX_ORDER:
            rec[f"n_{tx}"] = int(np.sum(groups == tx))
        rows.append(rec)
    return pd.DataFrame(rows)


def judge_q2(
    kruskal_rich: pd.DataFrame,
    kruskal_h: pd.DataFrame,
    permanova: pd.DataFrame,
) -> dict[str, object]:
    def _hits(df: pd.DataFrame) -> list[str]:
        out: list[str] = []
        for _, r in df.iterrows():
            p = float(r["p"]) if pd.notna(r["p"]) else float("nan")
            ns = [int(r[f"n_{t}"]) for t in TX_ORDER]
            if all(n >= 2 for n in ns) and np.isfinite(p) and p < 0.05:
                out.append(str(r["sex"]))
        return out

    h_rich = _hits(kruskal_rich)
    h_shan = _hits(kruskal_h)
    h_perm = _hits(permanova)
    if h_perm or h_shan:
        verdict = "hit"
    elif h_rich and not h_shan and not h_perm:
        verdict = "miss_richness_only"
    else:
        verdict = "miss"
    return {
        "q2": verdict,
        "q2_richness_hit_sexes": h_rich,
        "q2_shannon_hit_sexes": h_shan,
        "q2_permanova_hit_sexes": h_perm,
        "q2_rule": (
            "hit if Shannon Kruskal or Bray–Curtis PERMANOVA p<0.05 in ≥1 sex; "
            "richness-only is inventory, not preference"
        ),
    }


def fig_q2(meta: pd.DataFrame, tests: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(7.4, 6.4), sharex="col")
    metrics = (("richness", "COUNT  richness"), ("shannon_bits", "UNCERTAINTY  Shannon (bits)"))
    for row_i, (metric, ylab) in enumerate(metrics):
        sub_t = tests[tests["metric"] == metric]
        p_map = {str(r["sex"]): r["p"] for _, r in sub_t.iterrows()}
        for col_i, sex in enumerate(SEX_ORDER):
            ax = axes[row_i, col_i]
            sub = meta[meta["sex"] == sex]
            for i, tx in enumerate(TX_ORDER):
                y = sub.loc[sub["tx"] == tx, metric].to_numpy(dtype=np.float64)
                y = y[np.isfinite(y)]
                jitter = (np.arange(y.size) - (y.size - 1) / 2) * 0.02
                ax.scatter(
                    np.full(y.size, i) + jitter,
                    y,
                    s=22,
                    color=TX_COLORS[tx],
                    edgecolors="white",
                    linewidths=0.4,
                    zorder=2,
                )
                if y.size:
                    ax.plot([i - 0.22, i + 0.22], [np.median(y)] * 2, color="#222", lw=1.8, zorder=3)
            ax.set_xticks(range(len(TX_ORDER)))
            ax.set_xticklabels(list(TX_ORDER))
            p = p_map.get(sex, float("nan"))
            ptxt = "n/a" if p != p else f"p={p:.3g}"
            ax.set_title(f"{sex}  Kruskal {ptxt}", fontsize=9)
            if col_i == 0:
                ax.set_ylabel(ylab)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
    fig.suptitle("Q2 syllable composition · NOR_TX · novel_obj · raw · pilot model", fontsize=10)
    fig.text(
        0.01,
        0.01,
        "Grain: animal × novel_obj · frame-share composition · PERMANOVA is analogy-only (see run_summary)",
        fontsize=7,
        color="#555",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(out.with_suffix(".png"), dpi=150)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)


def run_q2(bout_csv: Path, out_dir: Path) -> dict[str, object]:
    bouts = pd.read_csv(bout_csv)
    meta, P, syll_ids = compositions_from_bouts(bouts)
    k_rich = kruskal_within_sex(meta, metric="richness")
    k_h = kruskal_within_sex(meta, metric="shannon_bits")
    perm = permanova_within_sex(meta, P)
    tests = pd.concat([k_rich, k_h], ignore_index=True)
    verdict = judge_q2(k_rich, k_h, perm)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta.to_csv(out_dir / "q2_animal_composition_scalars.csv", index=False)
    tests.to_csv(out_dir / "q2_within_sex_tx_kruskal.csv", index=False)
    perm.to_csv(out_dir / "q2_within_sex_tx_permanova_braycurtis.csv", index=False)
    np.savez_compressed(
        out_dir / "q2_compositions.npz",
        P=P,
        syllable_id=syll_ids,
        animal_id=meta["animal_id"].to_numpy(),
        sex=meta["sex"].to_numpy(),
        tx=meta["tx"].to_numpy(),
    )
    fig_q2(meta, tests, out_dir / "fig_q2_composition_scalars")
    summary = {
        "status": "ok",
        **{k: LOCKED[k] for k in ("phase_layer", "condition_layer", "model", "cleanup")},
        "question": "q2_syllable_composition_tx",
        "grain": "animal × NOR_TX × novel_obj; bout_frames pooled by raw_syllable_id",
        "bout_csv": str(bout_csv),
        "n_animals": int(len(meta)),
        "n_syllables_in_union": int(syll_ids.size),
        "operations": {
            "richness": "COUNT",
            "shannon_bits": "UNCERTAINTY",
            "braycurtis_permanova": "DIFFERENCE+TEST analogy-only",
        },
        **verdict,
        "q3": "parked",
        "kruskal_richness": k_rich.to_dict(orient="records"),
        "kruskal_shannon": k_h.to_dict(orient="records"),
        "permanova": perm.to_dict(orient="records"),
    }
    prev = out_dir / "run_summary.json"
    merged = summary
    if prev.exists():
        old = json.loads(prev.read_text(encoding="utf-8"))
        merged = {**old, "q2_block": summary, "q2": verdict["q2"]}
    (out_dir / "run_summary.json").write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
    ap.add_argument(
        "--bout-csv",
        type=Path,
        default=root
        / "_nor_object_mi"
        / LOCKED["model"]
        / "condition_ladder"
        / "ladder_bout_features.csv",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=root / "_nor_object_mi" / "simpler_first_NOR_TX_novel_obj",
    )
    args = ap.parse_args(argv)
    summary = run_q2(args.bout_csv, args.out_dir)
    print(json.dumps({k: summary[k] for k in summary if k not in {"kruskal_richness", "kruskal_shannon", "permanova"}}, indent=2))
    print(json.dumps({"kruskal_richness": summary["kruskal_richness"], "kruskal_shannon": summary["kruskal_shannon"], "permanova": [{k: r[k] for k in ("sex", "F", "p", "n") if k in r} for r in summary["permanova"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
