"""Bout occupancy MI: label id vs nearest-object prox category (fam / nvl / neither).

Within animal × phase on ``nvl_obj`` bouts:

    I(label; nearest_obj)

where ``label`` is ``raw_syllable_id`` or HDBSCAN ``cluster_id`` (mapped per model) and
``nearest_obj`` ∈ {fam, nvl, neither} from bout-mean spot distances at radius
``r_m`` (default 0.10 m). If both objects are within ``r_m``, the closer object wins;
ties go to fam. Circular-shift null matches ``compute_mi.py``.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Literal, Mapping, Sequence

import numpy as np
import pandas as pd

from nor_object_mi.compute_mi import (
    _null_circ_mean_p,
    _pooled_occupancy,
)
from nor_object_mi.pause_stim_mi import (
    DEFAULT_MODEL,
    PHASE_TAGS,
    find_bout_csv,
    load_bout_rows,
)
from nor_object_mi.simpler_first_da import apply_bh
from nor_object_mi.simpler_first_object_prox import NEAR_R_M
from nor_object_mi.simpler_first_session_paired import list_paramscan_models
from nor_object_mi.simpler_first_q1 import SEX_ORDER, CONDITION_ORDER, kruskal_within_sex

NEAREST_FAM = 0
NEAREST_NVL = 1
NEAREST_NEITHER = 2
NEAREST_LABELS: tuple[str, ...] = ("fam", "nvl", "neither")
DEFAULT_N_PERM = 200
LabelKind = Literal["syllable", "cluster"]
UNMAPPED_CLUSTER = -2
DEFAULT_SIG_DIR_NAME = "simpler_first_syllable_signatures"
CONSENSUS_METRIC_COLS: tuple[str, ...] = (
    "mi_mm",
    "excess",
    "H_syll",
    "H_stim",
    "frac_fam",
    "frac_nvl",
    "frac_neither",
    "null_circ_mean",
    "n_bouts",
)


def default_sig_dir(art_root: Path) -> Path:
    return art_root / DEFAULT_SIG_DIR_NAME


def load_cluster_map(sig_dir: Path, model: str) -> dict[int, int]:
    """Map raw_syllable_id → cluster_id for one kpMS model."""
    path = sig_dir / "syllable_prototypes_clustered.csv"
    proto = pd.read_csv(path, usecols=["model", "raw_syllable_id", "cluster_id"])
    sub = proto[proto["model"] == model]
    if sub.empty:
        raise ValueError(f"no cluster rows for model {model!r} in {path}")
    return {int(r.raw_syllable_id): int(r.cluster_id) for r in sub.itertuples(index=False)}


def label_for_row(
    row: Mapping[str, object],
    *,
    label_kind: LabelKind,
    cluster_map: Mapping[int, int] | None = None,
) -> int:
    raw = int(row["raw_syllable_id"])
    if label_kind == "syllable":
        return raw
    if cluster_map is None:
        raise ValueError("cluster_map required when label_kind='cluster'")
    return int(cluster_map.get(raw, UNMAPPED_CLUSTER))


def assign_nearest_prox_bin(d_fam: float, d_nvl: float, *, r_m: float = NEAR_R_M) -> int:
    """Return 0=fam, 1=nvl, 2=neither, -1=missing."""
    if not np.isfinite(d_fam) or not np.isfinite(d_nvl):
        return -1
    r = float(r_m)
    if d_fam >= r and d_nvl >= r:
        return NEAREST_NEITHER
    if d_fam <= d_nvl:
        return NEAREST_FAM
    return NEAREST_NVL


def nearest_bin_for_row(row: Mapping[str, object], *, r_m: float = NEAR_R_M) -> int:
    return assign_nearest_prox_bin(
        float(row["bout_mean_dist_fam_m"]),
        float(row["bout_mean_dist_nvl_m"]),
        r_m=r_m,
    )


def _streams_nearest_prox(
    rows: Sequence[Mapping[str, object]],
    *,
    animal_id: str,
    r_m: float = NEAR_R_M,
    label_kind: LabelKind = "syllable",
    cluster_map: Mapping[int, int] | None = None,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    by_trial: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if str(row["animal_id"]) != animal_id:
            continue
        if str(row.get("trial", "")) != "nvl_obj":
            continue
        by_trial[str(row["trial_key"])].append(row)

    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for trial, trows in by_trial.items():
        trows = sorted(trows, key=lambda r: int(r["bout_index"]))
        labels: list[int] = []
        stim: list[int] = []
        for r in trows:
            b = nearest_bin_for_row(r, r_m=r_m)
            if b < 0:
                continue
            labels.append(label_for_row(r, label_kind=label_kind, cluster_map=cluster_map))
            stim.append(int(b))
        if labels:
            out[trial] = (
                np.asarray(labels, dtype=np.int64),
                np.asarray(stim, dtype=np.int64),
            )
    return out


def category_fractions(stim: np.ndarray) -> dict[str, float]:
    n = int(stim.size)
    if n == 0:
        return {lab: float("nan") for lab in NEAREST_LABELS}
    out: dict[str, float] = {}
    for code, lab in enumerate(NEAREST_LABELS):
        out[lab] = float(np.mean(stim == code))
    return out


def compute_nearest_prox_mi(
    rows: list[dict[str, object]],
    *,
    r_m: float = NEAR_R_M,
    n_perm: int = DEFAULT_N_PERM,
    seed: int = 42,
    label_kind: LabelKind = "syllable",
    cluster_map: Mapping[int, int] | None = None,
) -> pd.DataFrame:
    if label_kind == "cluster" and cluster_map is None:
        raise ValueError("cluster_map required when label_kind='cluster'")

    animals = sorted({str(r["animal_id"]) for r in rows})
    meta_by_animal: dict[str, Mapping[str, object]] = {}
    for r in rows:
        meta_by_animal.setdefault(str(r["animal_id"]), r)

    rng = np.random.default_rng(seed)
    out_rows: list[dict[str, object]] = []
    for aid in animals:
        meta = meta_by_animal[aid]
        streams = _streams_nearest_prox(
            rows,
            animal_id=aid,
            r_m=r_m,
            label_kind=label_kind,
            cluster_map=cluster_map,
        )
        if not streams:
            continue
        mi_raw, mi_mm, h_syll, h_stim, n_bouts = _pooled_occupancy(streams)
        if n_bouts == 0:
            continue
        null_mean, null_p = _null_circ_mean_p(streams, observed_mm=mi_mm, n_perm=n_perm, rng=rng)
        stim_all = np.concatenate([s[1] for s in streams.values()])
        fr = category_fractions(stim_all)
        out_rows.append(
            {
                "animal_id": aid,
                "sex": meta["sex"],
                "condition": meta["condition"],
                "session": meta["session"],
                "label_kind": label_kind,
                "stim_var": "nearest_prox",
                "mi_type": "occupancy",
                "r_m": float(r_m),
                "n_bouts": n_bouts,
                "H_stim": h_stim,
                "H_syll": h_syll,
                "mi_raw": mi_raw,
                "mi_mm": mi_mm,
                "null_circ_mean": null_mean,
                "null_circ_p": null_p,
                "excess": float(mi_mm - null_mean),
                "frac_fam": fr["fam"],
                "frac_nvl": fr["nvl"],
                "frac_neither": fr["neither"],
            }
        )
    return pd.DataFrame(out_rows)


def default_out_dir(art_root: Path, model: str, *, label_kind: LabelKind = "syllable") -> Path:
    if label_kind == "cluster":
        return art_root / f"simpler_first_nearest_prox_cluster_mi__{model}"
    return art_root / f"simpler_first_nearest_prox_mi__{model}"


def default_ensemble_out_dir(art_root: Path, *, label_kind: LabelKind = "cluster") -> Path:
    if label_kind == "cluster":
        return art_root / "simpler_first_nearest_prox_cluster_mi__ensemble"
    return art_root / "simpler_first_nearest_prox_mi__ensemble"


def compute_model_mi_long(
    art_root: Path,
    model: str,
    *,
    r_m: float = NEAR_R_M,
    n_perm: int = DEFAULT_N_PERM,
    seed: int = 42,
    label_kind: LabelKind = "syllable",
    sig_dir: Path | None = None,
) -> pd.DataFrame:
    """Per-animal MI for one kpMS model across all phases."""
    cluster_map: dict[int, int] | None = None
    if label_kind == "cluster":
        sig = sig_dir or default_sig_dir(art_root)
        cluster_map = load_cluster_map(sig, model)

    parts: list[pd.DataFrame] = []
    for _session, tag in PHASE_TAGS:
        bout_path = find_bout_csv(art_root, model, tag)
        if bout_path is None:
            continue
        rows = load_bout_rows(bout_path)
        mi_df = compute_nearest_prox_mi(
            rows,
            r_m=r_m,
            n_perm=n_perm,
            seed=seed,
            label_kind=label_kind,
            cluster_map=cluster_map,
        )
        if not mi_df.empty:
            parts.append(mi_df)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    out.insert(0, "model", model)
    return out


def animal_median_across_models(mi_per_model: pd.DataFrame) -> pd.DataFrame:
    """Consensus MI: median across kpMS models per animal × phase."""
    need = {"animal_id", "sex", "condition", "session", "model", *CONSENSUS_METRIC_COLS}
    missing = need - set(mi_per_model.columns)
    if missing:
        raise KeyError(f"animal_median_across_models missing columns: {sorted(missing)}")
    keys = ["animal_id", "sex", "condition", "session"]
    out = mi_per_model.groupby(keys, as_index=False)[list(CONSENSUS_METRIC_COLS)].median()
    n_mod = mi_per_model.groupby(keys)["model"].nunique()
    if int(n_mod.min()) != int(n_mod.max()):
        raise AssertionError(f"uneven model coverage per animal: {n_mod.min()}-{n_mod.max()}")
    out["n_models"] = int(n_mod.min())
    if "label_kind" in mi_per_model.columns:
        out["label_kind"] = str(mi_per_model["label_kind"].iloc[0])
    out["stim_var"] = "nearest_prox"
    out["mi_type"] = "occupancy"
    out["r_m"] = float(mi_per_model["r_m"].iloc[0]) if "r_m" in mi_per_model.columns else float(NEAR_R_M)
    # consensus null p is not defined — leave NaN; use per-model agreement instead
    out["null_circ_p"] = float("nan")
    return out


def mi_stratum_agreement_by_model(tests_per_model: pd.DataFrame) -> pd.DataFrame:
    """Fraction of models with within-sex Kruskal p < 0.05 per phase × sex × metric."""
    if tests_per_model.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for (phase, sex, metric), g in tests_per_model.groupby(["session", "sex", "metric"], sort=True):
        n = int(g["model"].nunique())
        hit = g["hit_p05"].astype(bool)
        n_hit = int(hit.sum())
        p = pd.to_numeric(g["p"], errors="coerce")
        rows.append(
            {
                "session": phase,
                "sex": sex,
                "metric": metric,
                "n_models": n,
                "n_hit_p05": n_hit,
                "frac_hit": float(n_hit / n) if n else float("nan"),
                "median_p": float(p.median()) if p.notna().any() else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def _median_or_nan(s: pd.Series) -> float:
    v = pd.to_numeric(s, errors="coerce").to_numpy(dtype=np.float64)
    v = v[np.isfinite(v)]
    return float(np.median(v)) if v.size else float("nan")


def mi_stratum_summary(mi_long: pd.DataFrame) -> pd.DataFrame:
    """Descriptive median summaries per phase × sex × tx."""
    rows: list[dict[str, object]] = []
    keys = ("session", "sex", "condition")
    for key_vals, g in mi_long.groupby(list(keys), sort=True):
        phase, sex, condition = key_vals if isinstance(key_vals, tuple) else (key_vals,)
        p = pd.to_numeric(g["null_circ_p"], errors="coerce")
        rows.append(
            {
                "session": phase,
                "sex": sex,
                "condition": condition,
                "n_animals": int(g["animal_id"].nunique()),
                "median_mi_mm": _median_or_nan(g["mi_mm"]),
                "median_excess": _median_or_nan(g["excess"]),
                "median_H_syll": _median_or_nan(g["H_syll"]),
                "median_H_stim": _median_or_nan(g["H_stim"]),
                "median_frac_fam": _median_or_nan(g["frac_fam"]),
                "median_frac_nvl": _median_or_nan(g["frac_nvl"]),
                "median_frac_neither": _median_or_nan(g["frac_neither"]),
                "frac_sig_p05": float((p < 0.05).mean()) if len(p) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def mi_stratum_tests(mi_long: pd.DataFrame) -> pd.DataFrame:
    """Within-sex Kruskal on mi_mm / excess across tx, per phase."""
    rows: list[dict[str, object]] = []
    for phase in sorted(mi_long["session"].unique()):
        sub = mi_long[mi_long["session"] == phase]
        for metric in ("mi_mm", "excess"):
            tests = kruskal_within_sex(sub, metric=metric)
            for _, r in tests.iterrows():
                rows.append(
                    {
                        "session": phase,
                        "metric": metric,
                        "sex": r["sex"],
                        "test": r["test"],
                        "stat": r["stat"],
                        "p": r["p"],
                        "n": r["n"],
                        "median_noSD": r["median_noSD"],
                        "median_GHSD": r["median_GHSD"],
                        "median_RBSD": r["median_RBSD"],
                        "n_noSD": r["n_noSD"],
                        "n_GHSD": r["n_GHSD"],
                        "n_RBSD": r["n_RBSD"],
                        "hit_p05": bool(pd.notna(r["p"]) and float(r["p"]) < 0.05),
                    }
                )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = apply_bh(out, p_col="p", q_col="q_bh")
    out["hit_fdr05"] = out["q_bh"] < 0.05
    return out


def _phase_summary_from_mi(mi_long: pd.DataFrame) -> pd.DataFrame:
    phase_summary_rows: list[dict[str, object]] = []
    for phase, g in mi_long.groupby("session", sort=True):
        p = pd.to_numeric(g["null_circ_p"], errors="coerce")
        phase_summary_rows.append(
            {
                "session": phase,
                "n_animals": int(g["animal_id"].nunique()),
                "median_mi_mm": float(g["mi_mm"].median()),
                "median_excess": float(g["excess"].median()),
                "median_H_syll": float(g["H_syll"].median()),
                "median_H_stim": float(g["H_stim"].median()),
                "median_frac_fam": float(g["frac_fam"].median()),
                "median_frac_nvl": float(g["frac_nvl"].median()),
                "median_frac_neither": float(g["frac_neither"].median()),
                "frac_sig_p05": float((p < 0.05).mean()) if p.notna().any() else float("nan"),
            }
        )
    return pd.DataFrame(phase_summary_rows)


def write_run(
    *,
    art_root: Path,
    out_dir: Path,
    model: str = DEFAULT_MODEL,
    r_m: float = NEAR_R_M,
    n_perm: int = DEFAULT_N_PERM,
    seed: int = 42,
    label_kind: LabelKind = "syllable",
    sig_dir: Path | None = None,
) -> dict[str, object]:
    sig = sig_dir or default_sig_dir(art_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    phase_tags: list[dict[str, object]] = []
    for session, tag in PHASE_TAGS:
        bout_path = find_bout_csv(art_root, model, tag)
        if bout_path is None:
            phase_tags.append({"session": session, "tag": tag, "status": "missing"})
        else:
            phase_tags.append(
                {"session": session, "tag": tag, "bout_csv": str(bout_path), "status": "ok"}
            )

    mi_long = compute_model_mi_long(
        art_root,
        model,
        r_m=r_m,
        n_perm=n_perm,
        seed=seed,
        label_kind=label_kind,
        sig_dir=sig if label_kind == "cluster" else None,
    )
    if mi_long.empty:
        raise FileNotFoundError(f"no bout CSVs for model {model} under {art_root}")

    mi_out = mi_long.drop(columns=["model"])
    mi_out.to_csv(out_dir / "mi_per_animal.csv", index=False)

    phase_summary = _phase_summary_from_mi(mi_out)
    phase_summary.to_csv(out_dir / "mi_phase_summary.csv", index=False)

    stratum_summary = mi_stratum_summary(mi_out)
    stratum_summary.to_csv(out_dir / "mi_stratum_summary.csv", index=False)
    stratum_tests = mi_stratum_tests(mi_out)
    stratum_tests.to_csv(out_dir / "mi_stratum_tests_long.csv", index=False)

    cluster_map = load_cluster_map(sig, model) if label_kind == "cluster" else None
    label_claim = "cluster" if label_kind == "cluster" else "syllable"
    summary = {
        "art_root": str(art_root),
        "out_dir": str(out_dir),
        "model": model,
        "label_kind": label_kind,
        "sig_dir": str(sig) if label_kind == "cluster" else None,
        "n_clusters_mapped": len(set(cluster_map.values())) if cluster_map else None,
        "r_m": float(r_m),
        "n_perm": int(n_perm),
        "seed": int(seed),
        "phase_tags": phase_tags,
        "n_rows": int(len(mi_out)),
        "phase_summary": phase_summary.to_dict(orient="records"),
        "stratum_summary": stratum_summary.to_dict(orient="records"),
        "n_stratum_tests": int(len(stratum_tests)),
        "n_hit_kruskal_p05": int(stratum_tests["hit_p05"].sum()) if len(stratum_tests) else 0,
        "n_hit_kruskal_fdr": int(stratum_tests["hit_fdr05"].sum()) if "hit_fdr05" in stratum_tests.columns else 0,
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "INFO_nearest_prox_mi.md").write_text(
        f"""# Bout MI — {label_claim} vs nearest object (fam / nvl / neither)

**Claim:** I({label_claim}; nearest_obj) on `nvl_obj` bouts, r={r_m:g} m.

Categories: fam nearest within r; nvl nearest within r; neither when both distances ≥ r.
Dual-prox bouts go to the closer object (fam on tie).

Circular-shift null, n_perm={n_perm}. Pilot model `{model}`.
Label kind: `{label_kind}` (HDBSCAN map from `syllable_prototypes_clustered.csv` when cluster).

## Stratified outputs

| File | Content |
|------|---------|
| `mi_stratum_summary.csv` | phase × sex × tx medians |
| `mi_stratum_tests_long.csv` | within-sex Kruskal on mi_mm / excess across tx |
""",
        encoding="utf-8",
    )
    return summary


def write_ensemble_run(
    *,
    art_root: Path,
    out_dir: Path,
    r_m: float = NEAR_R_M,
    n_perm: int = DEFAULT_N_PERM,
    seed: int = 42,
    label_kind: LabelKind = "cluster",
    sig_dir: Path | None = None,
    models: Sequence[str] | None = None,
) -> dict[str, object]:
    """Run nearest-prox MI on all kpMS models; consensus = median across models."""
    if label_kind != "cluster":
        raise ValueError("ensemble run expects label_kind='cluster' (portable HDBSCAN ids)")

    sig = sig_dir or default_sig_dir(art_root)
    model_list = list(models) if models is not None else list_paramscan_models(art_root)
    if not model_list:
        raise FileNotFoundError(f"no paramscan models under {art_root}")

    out_dir.mkdir(parents=True, exist_ok=True)
    per_model_parts: list[pd.DataFrame] = []
    test_parts: list[pd.DataFrame] = []
    model_status: list[dict[str, object]] = []

    n_models = len(model_list)
    for i, model in enumerate(model_list, start=1):
        print(f"[{i}/{n_models}] {model} ...", flush=True)
        mi_long = compute_model_mi_long(
            art_root,
            model,
            r_m=r_m,
            n_perm=n_perm,
            seed=seed,
            label_kind=label_kind,
            sig_dir=sig,
        )
        if mi_long.empty:
            model_status.append({"model": model, "status": "empty"})
            continue
        per_model_parts.append(mi_long)
        mi_one = mi_long.drop(columns=["model"])
        tests = mi_stratum_tests(mi_one)
        tests.insert(0, "model", model)
        test_parts.append(tests)
        model_status.append({"model": model, "status": "ok", "n_rows": int(len(mi_long))})

    if not per_model_parts:
        raise FileNotFoundError("no per-model MI rows produced")

    mi_per_model = pd.concat(per_model_parts, ignore_index=True)
    mi_per_model.to_csv(out_dir / "mi_per_animal_per_model.csv", index=False)

    consensus = animal_median_across_models(mi_per_model)
    consensus.to_csv(out_dir / "mi_per_animal_consensus.csv", index=False)

    phase_summary = _phase_summary_from_mi(consensus)
    phase_summary.to_csv(out_dir / "mi_phase_summary.csv", index=False)

    stratum_summary = mi_stratum_summary(consensus)
    stratum_summary.to_csv(out_dir / "mi_stratum_summary.csv", index=False)
    stratum_tests = mi_stratum_tests(consensus)
    stratum_tests.to_csv(out_dir / "mi_stratum_tests_long.csv", index=False)

    tests_per_model = pd.concat(test_parts, ignore_index=True) if test_parts else pd.DataFrame()
    if not tests_per_model.empty:
        tests_per_model.to_csv(out_dir / "mi_stratum_tests_per_model.csv", index=False)
    agreement = mi_stratum_agreement_by_model(tests_per_model)
    if not agreement.empty:
        agreement.to_csv(out_dir / "mi_stratum_agreement_by_model.csv", index=False)

    summary = {
        "art_root": str(art_root),
        "out_dir": str(out_dir),
        "ensemble": True,
        "label_kind": label_kind,
        "sig_dir": str(sig),
        "n_models": len(model_list),
        "n_models_ok": int(sum(1 for s in model_status if s.get("status") == "ok")),
        "models": model_list,
        "model_status": model_status,
        "r_m": float(r_m),
        "n_perm": int(n_perm),
        "seed": int(seed),
        "n_rows_per_model": int(len(mi_per_model)),
        "n_rows_consensus": int(len(consensus)),
        "phase_summary": phase_summary.to_dict(orient="records"),
        "stratum_summary": stratum_summary.to_dict(orient="records"),
        "n_stratum_tests": int(len(stratum_tests)),
        "n_hit_kruskal_p05": int(stratum_tests["hit_p05"].sum()) if len(stratum_tests) else 0,
        "n_hit_kruskal_fdr": int(stratum_tests["hit_fdr05"].sum()) if "hit_fdr05" in stratum_tests.columns else 0,
        "agreement": agreement.to_dict(orient="records") if not agreement.empty else [],
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "INFO_nearest_prox_mi.md").write_text(
        f"""# Bout MI — ensemble cluster vs nearest object (fam / nvl / neither)

**Claim:** consensus I(cluster; nearest_obj) on `nvl_obj` bouts, r={r_m:g} m.

Per kpMS model: bout-stream MI with ensemble HDBSCAN ``cluster_id`` map.
Consensus per animal × phase: **median** across {len(model_list)} models (same grain as object-prox DR).

Categories: fam nearest within r; nvl nearest within r; neither when both distances ≥ r.
Circular-shift null per model, n_perm={n_perm}. Kruskal agreement = frac of models with p < 0.05.

## Outputs

| File | Content |
|------|---------|
| `mi_per_animal_per_model.csv` | long: model × animal × phase |
| `mi_per_animal_consensus.csv` | median across models |
| `mi_stratum_summary.csv` | consensus phase × sex × tx medians |
| `mi_stratum_tests_long.csv` | consensus within-sex Kruskal |
| `mi_stratum_tests_per_model.csv` | per-model Kruskal long |
| `mi_stratum_agreement_by_model.csv` | frac models hitting p < 0.05 |
""",
        encoding="utf-8",
    )
    return summary
