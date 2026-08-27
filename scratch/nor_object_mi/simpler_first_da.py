"""Paired differential abundance (DA) on presence/novelty condition steps.

Question (plain): which syllables change relative use when objects appear
(`no_obj → identical`) or when novel replaces identical (`identical → novel`)?

Not Shannon, not richness, not median Bray–Curtis. Operation: category contrast / DA
(analogy-only on syllables). Association: paired / repeated (same animal, two conditions).

Grain: animal × phase × condition_layer (full session). Same bout tables as
`simpler_first_presence.py`. Composition weighting: ``frame_share`` (sum
``bout_frames``; default) or ``bout_count`` (one count per bout).

Per syllable k:
    Δp_k = p_k(right) − p_k(left)
Wilcoxon signed-rank vs 0; Benjamini–Hochberg (BH) FDR within model × phase × step.
Descriptive companion: syllable share of L1 mass (SIMPER-ish BC contribution).

`raw_syllable_id` is comparable across phases *within one kpMS model*, not across models.

Default: all paramscan models × BL/TX/REC3hr/REC11hr → tests + within-model consistency.
Bout-count sibling folder: ``simpler_first_da_bout_count`` (``--weighting bout_count``).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from scipy import stats

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_presence import (  # noqa: E402
    PHASES,
    STEPS,
    WEIGHTINGS,
    build_animal_condition_table,
    wilcoxon_paired,
)
from nor_object_mi.simpler_first_q1 import LOCKED  # noqa: E402

DA_STEPS = ("no_obj->identical", "identical->novel", "no_obj->novel")
FDR_ALPHA = 0.05


def as_count_map(counts: object) -> dict[int, float]:
    if not isinstance(counts, dict):
        return {}
    out: dict[int, float] = {}
    for k, v in counts.items():
        try:
            sid = int(k)
        except (TypeError, ValueError):
            continue
        fv = float(v)
        if np.isfinite(fv) and fv > 0:
            out[sid] = fv
    return out


def shares_from_counts(counts: dict[int, float]) -> dict[int, float]:
    tot = float(sum(counts.values()))
    if tot <= 0:
        return {}
    return {k: v / tot for k, v in counts.items()}


def delta_p_and_bc_contrib(
    left_counts: dict[int, float],
    right_counts: dict[int, float],
) -> tuple[dict[int, float], dict[int, float], float]:
    """Δp_k, L1-share contribution, and Bray–Curtis on frame-share vectors.

    bc_contrib_frac[k] = |Δp_k| / ∑_j |Δp_j|  (0 if compositions are identical).
    Sums to 1 over k when any mass moved. Descriptive; not a test.
    """
    keys = sorted(set(left_counts) | set(right_counts))
    if not keys:
        return {}, {}, float("nan")
    sl = shares_from_counts(left_counts)
    sr = shares_from_counts(right_counts)
    if not sl or not sr:
        return {}, {}, float("nan")
    delta: dict[int, float] = {}
    abs_delta: dict[int, float] = {}
    l1 = 0.0
    for k in keys:
        d = float(sr.get(k, 0.0) - sl.get(k, 0.0))
        delta[k] = d
        ad = abs(d)
        abs_delta[k] = ad
        l1 += ad
    contrib = {k: (abs_delta[k] / l1 if l1 > 0 else 0.0) for k in keys}
    bc = 0.5 * l1  # both sides are probability vectors
    return delta, contrib, float(bc)


def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """BH q-values; NaNs are not allowed in the input list."""
    m = len(p_values)
    if m == 0:
        return []
    order = np.argsort(np.asarray(p_values, dtype=np.float64))
    ranked = np.asarray(p_values, dtype=np.float64)[order]
    q = ranked * m / (np.arange(m) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0.0, 1.0)
    out = np.full(m, np.nan, dtype=np.float64)
    out[order] = q
    return [float(x) for x in out]


def apply_bh(tests: pd.DataFrame, *, p_col: str = "p", q_col: str = "q_bh") -> pd.DataFrame:
    """Add q_bh / hit_p05 / hit_fdr05. FDR family = all finite-p rows in this table."""
    out = tests.copy()
    if out.empty:
        out[q_col] = pd.Series(dtype=float)
        out["hit_p05"] = pd.Series(dtype=bool)
        out["hit_fdr05"] = pd.Series(dtype=bool)
        return out
    p = pd.to_numeric(out[p_col], errors="coerce").to_numpy(dtype=np.float64)
    q = np.full(p.shape[0], np.nan, dtype=np.float64)
    ok = np.isfinite(p)
    if np.any(ok):
        q[ok] = np.asarray(benjamini_hochberg(p[ok].tolist()), dtype=np.float64)
    out[q_col] = q
    out["hit_p05"] = ok & (p < 0.05)
    out["hit_fdr05"] = np.isfinite(q) & (q < FDR_ALPHA)
    return out


def apply_bh_grouped(
    tests: pd.DataFrame,
    group_cols: Sequence[str],
    *,
    p_col: str = "p",
    q_col: str = "q_bh",
) -> pd.DataFrame:
    """BH separately within each group; preserves row order within groups."""
    if tests.empty:
        return apply_bh(tests, p_col=p_col, q_col=q_col)
    missing = [c for c in group_cols if c not in tests.columns]
    if missing:
        raise ValueError(f"apply_bh_grouped missing columns: {missing}")
    parts = [
        apply_bh(g, p_col=p_col, q_col=q_col)
        for _, g in tests.groupby(list(group_cols), sort=False)
    ]
    return pd.concat(parts, ignore_index=True)


def paired_da_deltas(
    ac: pd.DataFrame,
    *,
    step: str,
    left: str,
    right: str,
    pair_col: str,
) -> pd.DataFrame:
    """One row per animal × syllable: Δp and BC contribution for a paired step."""
    L = ac[ac[pair_col] == left].set_index("animal_id")
    R = ac[ac[pair_col] == right].set_index("animal_id")
    if L.index.has_duplicates or R.index.has_duplicates:
        raise ValueError(
            f"duplicate animal_id after pairing on {pair_col}; filter the other axis first"
        )
    common = sorted(set(L.index) & set(R.index))
    vocab: set[int] = set()
    left_maps: dict[str, dict[int, float]] = {}
    right_maps: dict[str, dict[int, float]] = {}
    for aid in common:
        cl = as_count_map(L.loc[aid, "counts"])
        cr = as_count_map(R.loc[aid, "counts"])
        left_maps[aid] = cl
        right_maps[aid] = cr
        vocab.update(cl)
        vocab.update(cr)
    sylls = sorted(vocab)
    extra_phase = "phase_layer" in ac.columns and pair_col != "phase_layer"
    extra_cond = "condition_layer" in ac.columns and pair_col != "condition_layer"
    rows: list[dict[str, object]] = []
    for aid in common:
        cl = left_maps[aid]
        cr = right_maps[aid]
        delta, contrib, bc = delta_p_and_bc_contrib(cl, cr)
        sl = shares_from_counts(cl)
        sr = shares_from_counts(cr)
        base: dict[str, object] = {
            "animal_id": aid,
            "sex": str(L.loc[aid, "sex"]),
            "tx": str(L.loc[aid, "tx"]),
            "step": step,
            "left": left,
            "right": right,
            "braycurtis": bc,
        }
        if extra_phase:
            base["phase_layer"] = str(L.loc[aid, "phase_layer"])
        if extra_cond:
            base["condition_layer"] = str(L.loc[aid, "condition_layer"])
        for sid in sylls:
            rows.append(
                {
                    **base,
                    "raw_syllable_id": sid,
                    "p_left": float(sl.get(sid, 0.0)),
                    "p_right": float(sr.get(sid, 0.0)),
                    "delta_p": float(delta.get(sid, 0.0)) if delta else float("nan"),
                    "bc_contrib_frac": float(contrib.get(sid, 0.0)) if contrib else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def da_tests_from_deltas(dtab: pd.DataFrame) -> pd.DataFrame:
    """Wilcoxon per syllable on Δp, then BH across syllables in this cell."""
    if dtab.empty:
        return apply_bh(
            pd.DataFrame(
                columns=[
                    "raw_syllable_id",
                    "n",
                    "n_nonzero",
                    "median_p_left",
                    "median_p_right",
                    "median_delta_p",
                    "frac_gt0",
                    "median_bc_contrib_frac",
                    "stat",
                    "p",
                    "test",
                    "question",
                    "sex",
                ]
            )
        )
    rows: list[dict[str, object]] = []
    for sid, g in dtab.groupby("raw_syllable_id", sort=True):
        dp = g["delta_p"].to_numpy(dtype=np.float64)
        rec = wilcoxon_paired(dp)
        finite = np.isfinite(dp)
        n_fin = int(np.sum(finite))
        rows.append(
            {
                "raw_syllable_id": int(sid),
                "n": rec["n"],
                "n_nonzero": int(np.sum(finite & (dp != 0))),
                "median_p_left": float(np.nanmedian(g["p_left"].to_numpy(dtype=np.float64))),
                "median_p_right": float(np.nanmedian(g["p_right"].to_numpy(dtype=np.float64))),
                "median_delta_p": float(np.nanmedian(dp)) if n_fin else float("nan"),
                "frac_gt0": float(np.mean(dp[finite] > 0)) if n_fin else float("nan"),
                "median_bc_contrib_frac": float(
                    np.nanmedian(g["bc_contrib_frac"].to_numpy(dtype=np.float64))
                ),
                "stat": rec["stat"],
                "p": rec["p"],
                "test": "wilcoxon_signed_rank",
                "question": "DA",
                "sex": "all",
            }
        )
    return apply_bh(pd.DataFrame(rows))


def da_tests_tx_sex_from_animal_deltas(dtab: pd.DataFrame, *, progress: bool = False) -> pd.DataFrame:
    """Wilcoxon + BH per syllable inside each model × phase × step × tx × sex.

    Does not pool tx or sex. Family for BH = syllables in that stratum (same as
    ``da_tests_from_deltas`` on the subset). Ids still are not portable across models.
    """
    need = {
        "model",
        "phase_layer",
        "step",
        "tx",
        "sex",
        "raw_syllable_id",
        "delta_p",
        "p_left",
        "p_right",
        "bc_contrib_frac",
    }
    missing = [c for c in need if c not in dtab.columns]
    if missing:
        raise ValueError(f"da_tests_tx_sex_from_animal_deltas missing columns: {missing}")
    if dtab.empty:
        return pd.DataFrame()
    keys = ["model", "phase_layer", "step", "tx", "sex", "raw_syllable_id"]
    has_left = "left" in dtab.columns
    has_right = "right" in dtab.columns
    cols = list(keys) + ["delta_p", "p_left", "p_right", "bc_contrib_frac"]
    if has_left:
        cols.append("left")
    if has_right:
        cols.append("right")
    dt = dtab.loc[:, cols].sort_values(keys, kind="mergesort")
    n = len(dt)
    if progress:
        print(f"  sorted {n} animal-syllable rows; Wilcoxon by stratum x syllable", flush=True)
    key_arr = dt[keys].to_numpy()
    if n == 0:
        return pd.DataFrame()
    change = np.empty(n, dtype=bool)
    change[0] = True
    change[1:] = np.any(key_arr[1:] != key_arr[:-1], axis=1)
    starts = np.flatnonzero(change)
    ends = np.append(starts[1:], n)
    dp_all = dt["delta_p"].to_numpy(dtype=np.float64)
    pl_all = dt["p_left"].to_numpy(dtype=np.float64)
    pr_all = dt["p_right"].to_numpy(dtype=np.float64)
    bc_all = dt["bc_contrib_frac"].to_numpy(dtype=np.float64)
    left_all = dt["left"].to_numpy() if has_left else None
    right_all = dt["right"].to_numpy() if has_right else None
    rows: list[dict[str, object]] = []
    n_grp = int(starts.size)
    report_every = max(1, n_grp // 20)
    for gi, (a, b) in enumerate(zip(starts, ends), start=1):
        if progress and (gi == 1 or gi % report_every == 0 or gi == n_grp):
            print(f"  Wilcoxon groups {gi}/{n_grp}", flush=True)
        rec_key = key_arr[a]
        dp = dp_all[a:b]
        d = dp[np.isfinite(dp)]
        if d.size < 2:
            rec = {"n": int(d.size), "stat": float("nan"), "p": float("nan")}
        elif np.all(d == 0):
            rec = {"n": int(d.size), "stat": float("nan"), "p": float("nan")}
        else:
            stat, p = stats.wilcoxon(
                d,
                alternative="two-sided",
                zero_method="wilcox",
                method="asymptotic",
            )
            rec = {"n": int(d.size), "stat": float(stat), "p": float(p)}
        finite = np.isfinite(dp)
        n_fin = int(np.sum(finite))
        row: dict[str, object] = {
            "model": str(rec_key[0]),
            "phase_layer": str(rec_key[1]),
            "step": str(rec_key[2]),
            "tx": str(rec_key[3]),
            "sex": str(rec_key[4]),
            "raw_syllable_id": int(rec_key[5]),
            "n": rec["n"],
            "n_nonzero": int(np.sum(finite & (dp != 0))),
            "median_p_left": float(np.nanmedian(pl_all[a:b])),
            "median_p_right": float(np.nanmedian(pr_all[a:b])),
            "median_delta_p": float(np.nanmedian(dp)) if n_fin else float("nan"),
            "frac_gt0": float(np.mean(dp[finite] > 0)) if n_fin else float("nan"),
            "median_bc_contrib_frac": float(np.nanmedian(bc_all[a:b])),
            "stat": rec["stat"],
            "p": rec["p"],
            "test": "wilcoxon_signed_rank",
            "question": "DA",
        }
        if has_left:
            row["left"] = str(left_all[a])
        if has_right:
            row["right"] = str(right_all[a])
        rows.append(row)
    out = pd.DataFrame(rows)
    return apply_bh_grouped(out, ["model", "phase_layer", "step", "tx", "sex"])


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 3 or b.size < 3:
        return float("nan")
    if np.allclose(a, a[0]) or np.allclose(b, b[0]):
        return float("nan")
    r, _p = stats.spearmanr(a, b)
    return float(r) if np.isfinite(r) else float("nan")


def jaccard(a: set[int], b: set[int]) -> float:
    if not a and not b:
        return float("nan")
    union = a | b
    return float(len(a & b) / len(union)) if union else float("nan")


def consistency_phase_pairs(
    tests: pd.DataFrame,
    *,
    facet_col: str,
    group_cols: tuple[str, ...],
    hit_col: str = "hit_fdr05",
) -> pd.DataFrame:
    """Pairwise Jaccard of FDR-hit sets + Spearman of median Δp, within each group."""
    need = set(group_cols) | {facet_col, "raw_syllable_id", "median_delta_p", hit_col}
    missing = [c for c in need if c not in tests.columns]
    if missing or tests.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for keys, g in tests.groupby(list(group_cols), sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        facets = sorted(g[facet_col].astype(str).unique())
        by_f = {f: g[g[facet_col].astype(str) == f] for f in facets}
        for i, fa in enumerate(facets):
            for fb in facets[i + 1 :]:
                ga, gb = by_f[fa], by_f[fb]
                hit_a = set(ga.loc[ga[hit_col].astype(bool), "raw_syllable_id"].astype(int))
                hit_b = set(gb.loc[gb[hit_col].astype(bool), "raw_syllable_id"].astype(int))
                ma = ga.set_index(ga["raw_syllable_id"].astype(int))["median_delta_p"]
                mb = gb.set_index(gb["raw_syllable_id"].astype(int))["median_delta_p"]
                common = sorted(set(ma.index) & set(mb.index))
                if common:
                    va = pd.to_numeric(ma.reindex(common), errors="coerce").to_numpy(dtype=np.float64)
                    vb = pd.to_numeric(mb.reindex(common), errors="coerce").to_numpy(dtype=np.float64)
                    ok = np.isfinite(va) & np.isfinite(vb)
                    rho = _spearman(va[ok], vb[ok])
                    n_sp = int(ok.sum())
                else:
                    rho = float("nan")
                    n_sp = 0
                rec = {c: k for c, k in zip(group_cols, keys)}
                rec.update(
                    {
                        f"{facet_col}_a": fa,
                        f"{facet_col}_b": fb,
                        "n_hit_a": int(len(hit_a)),
                        "n_hit_b": int(len(hit_b)),
                        "n_hit_both": int(len(hit_a & hit_b)),
                        "jaccard": jaccard(hit_a, hit_b),
                        "spearman_median_delta_p": rho,
                        "n_syllables_spearman": n_sp,
                    }
                )
                rows.append(rec)
    return pd.DataFrame(rows)


def syllable_persistence(
    tests: pd.DataFrame,
    *,
    facet_col: str,
    group_cols: tuple[str, ...],
    hit_col: str = "hit_fdr05",
) -> pd.DataFrame:
    """How often each syllable FDR-hits across facets, within a group (e.g. model × step)."""
    need = set(group_cols) | {facet_col, "raw_syllable_id", "median_delta_p", hit_col, "hit_p05"}
    if tests.empty or any(c not in tests.columns for c in need):
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for keys, g in tests.groupby(list(group_cols) + ["raw_syllable_id"], sort=True):
        *gkeys, sid = keys if isinstance(keys, tuple) else (keys,)
        med = pd.to_numeric(g["median_delta_p"], errors="coerce").to_numpy(dtype=np.float64)
        signs = np.sign(med)
        signs = signs[np.isfinite(signs) & (signs != 0)]
        if signs.size:
            maj = int(np.sign(np.sum(signs)))
            n_agree = int(np.sum(signs == maj))
        else:
            maj = 0
            n_agree = 0
        rec = {c: k for c, k in zip(group_cols, gkeys)}
        rec.update(
            {
                "raw_syllable_id": int(sid),
                "n_facets": int(g[facet_col].nunique()),
                "n_hit_fdr05": int(g[hit_col].astype(bool).sum()),
                "n_hit_p05": int(g["hit_p05"].astype(bool).sum()),
                "median_of_median_delta_p": float(np.nanmedian(med)) if med.size else float("nan"),
                "sign_majority": maj,
                "n_facets_agree_sign": n_agree,
                "frac_sign_agree": float(n_agree / signs.size) if signs.size else float("nan"),
            }
        )
        rows.append(rec)
    return pd.DataFrame(rows)


def run_phase_da(
    bout_csv: Path,
    phase: str,
    *,
    weighting: str = "frame_share",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if weighting not in WEIGHTINGS:
        raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {weighting!r}")
    bouts = pd.read_csv(bout_csv)
    ac = build_animal_condition_table(bouts, phase_layer=phase, weighting=weighting)
    test_parts: list[pd.DataFrame] = []
    delta_parts: list[pd.DataFrame] = []
    for step, left, right in STEPS:
        dtab = paired_da_deltas(
            ac, step=step, left=left, right=right, pair_col="condition_layer"
        )
        if dtab.empty:
            continue
        tests = da_tests_from_deltas(dtab)
        tests.insert(0, "phase_layer", phase)
        tests.insert(1, "step", step)
        tests.insert(2, "left", left)
        tests.insert(3, "right", right)
        tests.insert(4, "weighting", weighting)
        test_parts.append(tests)
        dtab = dtab.copy()
        dtab["phase_layer"] = phase
        dtab["weighting"] = weighting
        delta_parts.append(dtab)
    tests_df = pd.concat(test_parts, ignore_index=True) if test_parts else pd.DataFrame()
    deltas_df = pd.concat(delta_parts, ignore_index=True) if delta_parts else pd.DataFrame()
    return tests_df, deltas_df


def _info_bout_count_md() -> str:
    return """# INFO — simpler-first DA (bout_count weighting)

Sibling of `simpler_first_da/` with composition = **bout counts** (one vote per bout),
not frame-shares. Same grain, steps, BH families, and id rules.

## Δp

$$
p_k = \\frac{\\text{bouts labeled } k}{\\text{session bouts}}, \\qquad
\\Delta p_k = p_k(\\mathrm{right}) - p_k(\\mathrm{left})
$$

Long syllables no longer get extra mass from duration. Compare to frame_share
volcanos: pause/still winners often shrink under bout_count.

## Inputs

Same `ladder_bout_features.csv` as the frame_share run.

## Not

Not Shannon. Not a second scientific claim until compared to frame_share.
"""


def _copy_dictionary(out: Path, *, weighting: str) -> None:
    tag = "da"
    if weighting == "bout_count":
        (out / "INFO_da.md").write_text(_info_bout_count_md(), encoding="utf-8")
        return
    src = Path(__file__).with_name(f"INFO_{tag}.md")
    if not src.exists():
        return
    text = src.read_text(encoding="utf-8")
    today = date.today().isoformat()
    text, _n = re.subn(
        r"(?m)^(\|\s*Generated\s*\|\s*)\d{4}-\d{2}-\d{2}(\s*\|)\s*$",
        rf"\g<1>{today}\2",
        text,
        count=1,
    )
    (out / f"INFO_{tag}.md").write_text(text, encoding="utf-8")
    legacy = out / "DATA_DICTIONARY.md"
    if legacy.exists():
        legacy.unlink()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
    ap.add_argument("--ensemble-root", type=Path, default=root)
    ap.add_argument(
        "--model",
        type=str,
        default=None,
        help="Single model; default = all paramscan_* with bout CSVs",
    )
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument(
        "--weighting",
        choices=list(WEIGHTINGS),
        default="frame_share",
        help="Composition: frame_share (default) or bout_count",
    )
    ap.add_argument(
        "--write-deltas",
        action="store_true",
        help="Write per-animal × syllable Δp CSV (large)",
    )
    args = ap.parse_args(argv)

    art_root = args.ensemble_root / "_nor_object_mi"
    default_name = (
        "simpler_first_da_bout_count" if args.weighting == "bout_count" else "simpler_first_da"
    )
    out = args.out_dir or (art_root / default_name)
    out.mkdir(parents=True, exist_ok=True)
    _copy_dictionary(out, weighting=args.weighting)

    # Bout ladders may live under art_root/paramscan_* or art_root/archive/paramscan_*.
    model_roots: list[Path] = []
    for base in (art_root, art_root / "archive"):
        if not base.is_dir():
            continue
        for p in sorted(base.glob("paramscan_*")):
            if p.is_dir() and any(
                (p / tag / "ladder_bout_features.csv").exists() for _, tag in PHASES
            ):
                model_roots.append(p)
    # Prefer non-archive when both exist (same model name).
    by_name: dict[str, Path] = {}
    for p in model_roots:
        name = p.name
        if name not in by_name or "archive" not in p.parts:
            by_name[name] = p

    if args.model:
        if args.model not in by_name:
            raise SystemExit(f"model not found with bout ladders: {args.model}")
        model_paths = [by_name[args.model]]
    else:
        model_paths = [by_name[k] for k in sorted(by_name)]

    all_tests: list[pd.DataFrame] = []
    all_deltas: list[pd.DataFrame] = []
    n_jobs = len(model_paths) * len(PHASES)
    done = 0
    for art in model_paths:
        model = art.name
        for phase, tag in PHASES:
            done += 1
            bout_csv = art / tag / "ladder_bout_features.csv"
            if not bout_csv.exists():
                print(f"[{done}/{n_jobs}] MISSING {model} {phase}", flush=True)
                continue
            print(
                f"[{done}/{n_jobs}] {model} {phase} weighting={args.weighting}",
                flush=True,
            )
            tests, deltas = run_phase_da(bout_csv, phase, weighting=args.weighting)
            if tests.empty:
                continue
            tests.insert(0, "model", model)
            all_tests.append(tests)
            if args.write_deltas and not deltas.empty:
                deltas.insert(0, "model", model)
                all_deltas.append(deltas)

    tests_df = pd.concat(all_tests, ignore_index=True) if all_tests else pd.DataFrame()
    tests_path = out / "da_syllable_tests_long.csv"
    tests_df.to_csv(tests_path, index=False)

    if all_deltas:
        pd.concat(all_deltas, ignore_index=True).to_csv(
            out / "da_syllable_deltas_per_animal.csv", index=False
        )

    pair_path = out / "da_consistency_phase_pairs.csv"
    persist_path = out / "da_syllable_phase_persistence.csv"
    pairs = consistency_phase_pairs(
        tests_df, facet_col="phase_layer", group_cols=("model", "step")
    )
    persist = syllable_persistence(
        tests_df, facet_col="phase_layer", group_cols=("model", "step")
    )
    if not pairs.empty:
        pairs.to_csv(pair_path, index=False)
    if not persist.empty:
        persist.to_csv(persist_path, index=False)

    n_fdr = int(tests_df["hit_fdr05"].sum()) if not tests_df.empty else 0
    models = [p.name for p in model_paths]
    payload = {
        "n_models": len(models),
        "models": models,
        "phases": [p for p, _ in PHASES],
        "steps": list(DA_STEPS),
        "weighting": args.weighting,
        "n_test_rows": int(len(tests_df)),
        "n_hit_fdr05": n_fdr,
        "tests_path": str(tests_path),
        "consistency_path": str(pair_path),
        "persistence_path": str(persist_path),
        "bout_source": "archive/" if any("archive" in str(p) for p in model_paths) else "art_root/",
        "hit_rule": (
            "sex=all Wilcoxon on paired Δp_k, BH FDR q<0.05 within model × phase × step "
            f"(animals pooled across tx). weighting={args.weighting}."
        ),
        "id_portability": "raw_syllable_id aligned within a kpMS model across phases; not across models",
        "pilot_model_note": str(LOCKED["model"]),
        "sibling_frame_share": str(art_root / "simpler_first_da"),
    }
    (out / "run_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "path": str(out),
                "weighting": args.weighting,
                "n_models": len(models),
                "n_test_rows": int(len(tests_df)),
                "n_hit_fdr05": n_fdr,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
