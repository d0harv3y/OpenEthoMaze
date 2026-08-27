"""Near-object grain: bout_mean_dist_any < r, then redefined Q1 + Q2.

Grain declaration
-----------------
animal × phase × novel_obj × spot_bout_mean_any < 0.10 m (raw)

Gate A (locked): any-object distance, fixed r = 0.10 m.
Q1 redefined: among gated bouts, novelty preference (not full-session Δ_prox).
Q2: syllable composition on the same gated frames.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_q1 import (  # noqa: E402
    LOCKED,
    kruskal_within_sex,
    weighted_mean,
)
from nor_object_mi.simpler_first_q2 import (  # noqa: E402
    compositions_from_bouts,
    judge_q2,
    permanova_within_sex,
)

NEAR_R_M = 0.10
MIN_NEAR_FRAMES = 50  # fail loud if animal has fewer gated frames
CONDITION = "novel_obj"

PHASES: tuple[tuple[str, str], ...] = (
    ("NOR_BL", "condition_ladder_NOR_BL"),
    ("NOR_TX", "condition_ladder"),
    ("NOR_REC3hr", "condition_ladder_NOR_REC3hr"),
    ("NOR_REC11hr", "condition_ladder_NOR_REC11hr"),
)

GRAIN = (
    f"animal × {{phase}} × {CONDITION} × "
    f"spot_bout_mean_any < {NEAR_R_M:g} m (raw); min_near_frames={MIN_NEAR_FRAMES}"
)


def gate_near_any(
    bouts: pd.DataFrame,
    *,
    phase_layer: str,
    r_m: float = NEAR_R_M,
    condition_layer: str = CONDITION,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (session slice, near-gated slice) for one phase."""
    sess = bouts[
        (bouts["phase_layer"] == phase_layer) & (bouts["condition_layer"] == condition_layer)
    ].copy()
    if sess.empty:
        return sess, sess.iloc[0:0].copy()
    sess["animal_id"] = sess["animal_id"].astype(str)
    d_any = sess["bout_mean_dist_any_m"].to_numpy(dtype=np.float64)
    near = sess[np.isfinite(d_any) & (d_any < float(r_m))].copy()
    return sess, near


def animal_near_q1(
    sess: pd.DataFrame,
    near: pd.DataFrame,
    *,
    phase_layer: str,
    min_near_frames: int = MIN_NEAR_FRAMES,
) -> pd.DataFrame:
    """Per-animal redefined Q1 metrics on the near-any gate.

    Primary: ``pref_nvl_among_near`` = frame-weighted P(d_nvl < d_fam | near).
    Companions: ``delta_prox_among_near``, ``frac_near``, ``n_near_frames``.
    """
    meta = (
        sess.groupby("animal_id", sort=True)
        .agg(sex=("sex", "first"), tx=("tx", "first"), n_sess_frames=("bout_frames", "sum"))
        .reset_index()
    )
    rows: list[dict[str, object]] = []
    near_by = {aid: g for aid, g in near.groupby("animal_id")}
    for _, m in meta.iterrows():
        aid = str(m["animal_id"])
        g = near_by.get(aid)
        n_sess = int(m["n_sess_frames"])
        if g is None or g.empty:
            rows.append(
                {
                    "animal_id": aid,
                    "sex": str(m["sex"]),
                    "tx": str(m["tx"]),
                    "phase_layer": phase_layer,
                    "n_sess_frames": n_sess,
                    "n_near_frames": 0,
                    "frac_near": 0.0,
                    "pref_nvl_among_near": float("nan"),
                    "delta_prox_among_near": float("nan"),
                    "kept": False,
                }
            )
            continue
        w = g["bout_frames"].to_numpy(dtype=np.float64)
        d_fam = g["bout_mean_dist_fam_m"].to_numpy(dtype=np.float64)
        d_nvl = g["bout_mean_dist_nvl_m"].to_numpy(dtype=np.float64)
        n_near = int(np.nansum(w))
        ok = np.isfinite(d_fam) & np.isfinite(d_nvl) & np.isfinite(w) & (w > 0)
        pref = (
            float(np.sum((d_nvl[ok] < d_fam[ok]) * w[ok]) / np.sum(w[ok])) if np.any(ok) else float("nan")
        )
        d_fam_w = weighted_mean(d_fam, w)
        d_nvl_w = weighted_mean(d_nvl, w)
        kept = n_near >= int(min_near_frames)
        rows.append(
            {
                "animal_id": aid,
                "sex": str(m["sex"]),
                "tx": str(m["tx"]),
                "phase_layer": phase_layer,
                "n_sess_frames": n_sess,
                "n_near_frames": n_near,
                "frac_near": float(n_near / n_sess) if n_sess > 0 else float("nan"),
                "pref_nvl_among_near": pref,
                "delta_prox_among_near": d_fam_w - d_nvl_w,
                "kept": kept,
            }
        )
    return pd.DataFrame(rows)


def run_phase_near(
    bout_csv: Path,
    phase: str,
    *,
    r_m: float = NEAR_R_M,
    min_near_frames: int = MIN_NEAR_FRAMES,
) -> tuple[list[dict[str, object]], dict[str, object], pd.DataFrame, pd.DataFrame]:
    bouts = pd.read_csv(bout_csv)
    sess, near = gate_near_any(bouts, phase_layer=phase, r_m=r_m)
    q1 = animal_near_q1(sess, near, phase_layer=phase, min_near_frames=min_near_frames)
    kept = q1[q1["kept"]].copy()

    long_rows: list[dict[str, object]] = []

    def _add_kruskal(question: str, metric: str, df: pd.DataFrame) -> pd.DataFrame:
        tests = kruskal_within_sex(df, metric=metric)
        for _, r in tests.iterrows():
            long_rows.append(
                {
                    "phase_layer": phase,
                    "question": question,
                    "metric": metric,
                    "grain": GRAIN.format(phase=phase),
                    "r_m": r_m,
                    "sex": r["sex"],
                    "test": r["test"],
                    "stat": r["stat"],
                    "p": r["p"],
                    "n": r["n"],
                    "n_noSD": r["n_noSD"],
                    "n_GHSD": r["n_GHSD"],
                    "n_RBSD": r["n_RBSD"],
                    "median_noSD": r["median_noSD"],
                    "median_GHSD": r["median_GHSD"],
                    "median_RBSD": r["median_RBSD"],
                    "F": "",
                    "n_perm": "",
                    "hit_p05": bool(pd.notna(r["p"]) and float(r["p"]) < 0.05),
                }
            )
        return tests

    # Q1: preference among near (primary) + engagement companion
    k_pref = _add_kruskal("q1_near", "pref_nvl_among_near", kept)
    k_dprox = _add_kruskal("q1_near", "delta_prox_among_near", kept)
    k_frac = _add_kruskal("q1_near", "frac_near", q1)  # all animals; 0 if never near

    def _hit_sexes(tests: pd.DataFrame) -> list[str]:
        return [
            str(r["sex"])
            for _, r in tests.iterrows()
            if pd.notna(r["p"]) and float(r["p"]) < 0.05
        ]

    v_pref = {
        "q1_pref": "hit" if _hit_sexes(k_pref) else "miss",
        "q1_pref_hit_sexes": _hit_sexes(k_pref),
        "q1_delta_prox_among_near": "hit" if _hit_sexes(k_dprox) else "miss",
        "q1_delta_prox_hit_sexes": _hit_sexes(k_dprox),
        "q1_frac_near": "hit" if _hit_sexes(k_frac) else "miss",
        "q1_frac_near_hit_sexes": _hit_sexes(k_frac),
    }

    # Q2 on gated bouts for kept animals only
    near_kept = near[near["animal_id"].astype(str).isin(set(kept["animal_id"].astype(str)))].copy()
    # compositions_from_bouts re-filters by phase/condition — pass full near_kept with those cols
    if near_kept.empty:
        meta = pd.DataFrame()
        P = np.zeros((0, 0))
        syll_ids = np.array([], dtype=np.int64)
        k_rich = pd.DataFrame()
        k_h = pd.DataFrame()
        perm = pd.DataFrame()
        v2 = {
            "q2": "miss",
            "q2_richness_hit_sexes": [],
            "q2_shannon_hit_sexes": [],
            "q2_permanova_hit_sexes": [],
        }
    else:
        meta, P, syll_ids = compositions_from_bouts(
            near_kept, phase_layer=phase, condition_layer=CONDITION
        )
        # Restrict to kept (compositions_from_bouts already only sees near_kept)
        k_rich = kruskal_within_sex(meta, metric="richness")
        k_h = kruskal_within_sex(meta, metric="shannon_bits")
        perm = permanova_within_sex(meta, P)
        for _, r in k_rich.iterrows():
            long_rows.append(
                {
                    "phase_layer": phase,
                    "question": "q2_near",
                    "metric": "richness",
                    "grain": GRAIN.format(phase=phase),
                    "r_m": r_m,
                    "sex": r["sex"],
                    "test": r["test"],
                    "stat": r["stat"],
                    "p": r["p"],
                    "n": r["n"],
                    "n_noSD": r["n_noSD"],
                    "n_GHSD": r["n_GHSD"],
                    "n_RBSD": r["n_RBSD"],
                    "median_noSD": r["median_noSD"],
                    "median_GHSD": r["median_GHSD"],
                    "median_RBSD": r["median_RBSD"],
                    "F": "",
                    "n_perm": "",
                    "hit_p05": bool(pd.notna(r["p"]) and float(r["p"]) < 0.05),
                }
            )
        for _, r in k_h.iterrows():
            long_rows.append(
                {
                    "phase_layer": phase,
                    "question": "q2_near",
                    "metric": "shannon_bits",
                    "grain": GRAIN.format(phase=phase),
                    "r_m": r_m,
                    "sex": r["sex"],
                    "test": r["test"],
                    "stat": r["stat"],
                    "p": r["p"],
                    "n": r["n"],
                    "n_noSD": r["n_noSD"],
                    "n_GHSD": r["n_GHSD"],
                    "n_RBSD": r["n_RBSD"],
                    "median_noSD": r["median_noSD"],
                    "median_GHSD": r["median_GHSD"],
                    "median_RBSD": r["median_RBSD"],
                    "F": "",
                    "n_perm": "",
                    "hit_p05": bool(pd.notna(r["p"]) and float(r["p"]) < 0.05),
                }
            )
        for _, r in perm.iterrows():
            long_rows.append(
                {
                    "phase_layer": phase,
                    "question": "q2_near",
                    "metric": "braycurtis_composition",
                    "grain": GRAIN.format(phase=phase),
                    "r_m": r_m,
                    "sex": r["sex"],
                    "test": "permanova",
                    "stat": "",
                    "p": r["p"],
                    "n": r["n"],
                    "n_noSD": r["n_noSD"],
                    "n_GHSD": r["n_GHSD"],
                    "n_RBSD": r["n_RBSD"],
                    "median_noSD": "",
                    "median_GHSD": "",
                    "median_RBSD": "",
                    "F": r["F"],
                    "n_perm": r["n_perm"],
                    "hit_p05": bool(pd.notna(r["p"]) and float(r["p"]) < 0.05),
                }
            )
        v2 = judge_q2(k_rich, k_h, perm)

    summary = {
        "status": "ok",
        "phase_layer": phase,
        "grain": GRAIN.format(phase=phase),
        "r_m": r_m,
        "min_near_frames": min_near_frames,
        "n_animals_session": int(len(q1)),
        "n_animals_kept": int(len(kept)),
        "n_dropped_short_near": int((~q1["kept"]).sum()),
        "median_frac_near": float(q1["frac_near"].median()) if len(q1) else float("nan"),
        "n_syllables_near": int(syll_ids.size) if hasattr(syll_ids, "size") else 0,
        "hope": "baseline_should_be_quiet" if phase == "NOR_BL" else "tx_or_recovery_may_hit",
        **v_pref,
        "q2": v2.get("q2", "miss"),
        "q2_richness_hit_sexes": v2.get("q2_richness_hit_sexes", []),
        "q2_shannon_hit_sexes": v2.get("q2_shannon_hit_sexes", []),
        "q2_permanova_hit_sexes": v2.get("q2_permanova_hit_sexes", []),
        "pattern_ok": (
            (
                v_pref["q1_pref"] == "miss"
                and v_pref["q1_frac_near"] == "miss"
                and v2.get("q2") in {"miss", "miss_richness_only"}
            )
            if phase == "NOR_BL"
            else None
        ),
    }
    return long_rows, summary, q1, meta if isinstance(meta, pd.DataFrame) else pd.DataFrame()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
    ap.add_argument("--ensemble-root", type=Path, default=root)
    ap.add_argument("--model", type=str, default=str(LOCKED["model"]))
    ap.add_argument("--r-m", type=float, default=NEAR_R_M)
    ap.add_argument("--min-near-frames", type=int, default=MIN_NEAR_FRAMES)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    art = args.ensemble_root / "_nor_object_mi" / args.model
    out = args.out_dir or (
        args.ensemble_root / "_nor_object_mi" / "simpler_first_near_any_0p10"
    )
    out.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    animal_parts: list[pd.DataFrame] = []

    for phase, tag in PHASES:
        bout_csv = art / tag / "ladder_bout_features.csv"
        if not bout_csv.exists():
            summaries.append({"phase_layer": phase, "status": "missing_bout_csv"})
            print(f"MISSING {phase}", flush=True)
            continue
        print(f"near-grain {phase} r={args.r_m} …", flush=True)
        rows, summary, q1, _meta = run_phase_near(
            bout_csv,
            phase,
            r_m=float(args.r_m),
            min_near_frames=int(args.min_near_frames),
        )
        all_rows.extend(rows)
        summaries.append(summary)
        animal_parts.append(q1)
        print(
            f"  kept={summary['n_animals_kept']}/{summary['n_animals_session']} "
            f"q1_pref={summary['q1_pref']} frac_near={summary['q1_frac_near']} "
            f"q2={summary['q2']}",
            flush=True,
        )

    long_df = pd.DataFrame(all_rows)
    long_path = out / "q1_q2_near_phase_tests_long.csv"
    long_df.to_csv(long_path, index=False)
    if animal_parts:
        pd.concat(animal_parts, ignore_index=True).to_csv(
            out / "q1_animal_near_metrics.csv", index=False
        )
    payload = {
        "model": args.model,
        "cleanup": "raw",
        "condition_layer": CONDITION,
        "gate": "bout_mean_dist_any_m",
        "r_m": float(args.r_m),
        "min_near_frames": int(args.min_near_frames),
        "grain_template": GRAIN,
        "q1_primary": "pref_nvl_among_near",
        "q1_companions": ["delta_prox_among_near", "frac_near"],
        "per_phase": summaries,
        "path": str(long_path),
        "hope": "BL quiet; TX or REC3/REC11 may show tx hits",
    }
    (out / "run_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if not long_df.empty:
        show = long_df.copy()
        show["p"] = show["p"].map(lambda x: f"{float(x):.3g}" if pd.notna(x) and x != "" else "")
        print(
            show[
                ["phase_layer", "question", "metric", "sex", "test", "p", "hit_p05", "n"]
            ].to_string(index=False)
        )
    print(json.dumps({"path": str(long_path), "per_phase": summaries}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
