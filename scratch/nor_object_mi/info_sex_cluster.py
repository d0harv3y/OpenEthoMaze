"""INFO: does sex reduce uncertainty about cluster id (within tx, across phases)?

Between-animal association on ``nvl_obj`` bouts. For each animal × tx stratum,
pool cluster-labeled bout frames across all NOR phases; Y = frame-dominant HDBSCAN
``cluster_id`` (ensemble mode across kpMS models). X = sex (F/M).

    I(sex; dominant_cluster)   within tx, phases pooled
    I(sex; dominant_cluster)   within tx × phase   (companion lattice)
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from nor_object_mi._pub_style import SESSIONS, CONDITION_ORDER
from nor_object_mi.info_dr_pause_delta import MIN_N_FOR_INFO, pair_mi_mm
from nor_object_mi.nearest_prox_mi import default_sig_dir, label_for_row, load_cluster_map
from nor_object_mi.pause_stim_mi import find_bout_csv, load_bout_rows
from nor_object_mi.simpler_first_da import apply_bh
from nor_object_mi.simpler_first_object_prox import CONDITION, SESSIONS as PHASE_TAGS
from nor_object_mi.simpler_first_phase_paired import list_paramscan_models

DEFAULT_N_PERM = 9999
QUESTION_DOMINANT = "info_sex_vs_dominant_cluster"
QUESTION_COMPOSITION = "info_sex_vs_cluster_composition"
SEX_CODE: dict[str, int] = {"F": 0, "M": 1}
DEFAULT_TOP_K = 4
DEFAULT_FRAC_BINS = 5


def default_out_dir(ensemble_root: Path) -> Path:
    return ensemble_root / "_nor_object_mi" / "simpler_first_info_sex_cluster"


def _accumulate_cluster_frames(
    rows: Sequence[Mapping[str, object]],
    *,
    cluster_map: Mapping[int, int],
    pool_phases: bool,
) -> dict[tuple[str, str, str | None], dict[int, float]]:
    """Frames per (animal_id, condition, phase_or_none) × cluster_id."""
    acc: dict[tuple[str, str, str | None], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        if str(row.get("trial", "")) != CONDITION:
            continue
        phase = str(row["session"])
        aid = str(row["animal_id"])
        condition = str(row["condition"])
        w = float(row.get("bout_frames", 1) or 1)
        if not np.isfinite(w) or w <= 0:
            w = 1.0
        cid = label_for_row(row, label_kind="cluster", cluster_map=cluster_map)
        keys: list[tuple[str, str, str | None]] = [(aid, condition, phase)]
        if pool_phases:
            keys.append((aid, condition, None))
        for key in keys:
            acc[key][cid] += w
    return acc


def _dominant_from_acc(acc: Mapping[int, float]) -> int:
    if not acc:
        return -999
    return int(max(acc.items(), key=lambda kv: (kv[1], -kv[0]))[0])


def model_cluster_frames_long(
    art_root: Path,
    model: str,
    *,
    sig_dir: Path,
    pool_phases: bool = True,
) -> pd.DataFrame:
    """Long frame counts per animal × tx (× phase) × cluster_id for one model."""
    cluster_map = load_cluster_map(sig_dir, model)
    sex_by_animal: dict[str, str] = {}
    acc: dict[tuple[str, str, str | None], dict[int, float]] = defaultdict(lambda: defaultdict(float))

    for _session, tag in PHASE_TAGS:
        bout_path = find_bout_csv(art_root, model, tag)
        if bout_path is None:
            continue
        rows = load_bout_rows(bout_path)
        for row in rows:
            sex_by_animal.setdefault(str(row["animal_id"]), str(row["sex"]))
        part = _accumulate_cluster_frames(rows, cluster_map=cluster_map, pool_phases=pool_phases)
        for (aid, condition, phase_key), counts in part.items():
            for cid, w in counts.items():
                acc[(aid, condition, phase_key)][cid] += w

    rows_out: list[dict[str, object]] = []
    for (aid, condition, phase_key), counts in acc.items():
        sex = sex_by_animal.get(aid, "")
        phase_label = phase_key if phase_key is not None else "ALL_SESSIONS"
        for cid, w in counts.items():
            rows_out.append(
                {
                    "model": model,
                    "animal_id": aid,
                    "sex": sex,
                    "condition": condition,
                    "session": phase_label,
                    "cluster_id": int(cid),
                    "n_bout_frames": float(w),
                }
            )
    return pd.DataFrame(rows_out)


def model_dominant_clusters(
    art_root: Path,
    model: str,
    *,
    sig_dir: Path,
    pool_phases: bool = True,
) -> pd.DataFrame:
    """One row per animal × tx (× phase): dominant cluster for one model."""
    long = model_cluster_frames_long(art_root, model, sig_dir=sig_dir, pool_phases=pool_phases)
    if long.empty:
        return long
    rows_out: list[dict[str, object]] = []
    keys = ["model", "animal_id", "sex", "condition", "session"]
    for key_vals, g in long.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        counts = dict(zip(g["cluster_id"].astype(int), g["n_bout_frames"].astype(float)))
        rows_out.append(
            {
                **key_map,
                "dominant_cluster_id": _dominant_from_acc(counts),
                "n_clusters_used": int(len(counts)),
                "n_bout_frames": float(sum(counts.values())),
            }
        )
    return pd.DataFrame(rows_out)


def consensus_dominant_clusters(per_model: pd.DataFrame) -> pd.DataFrame:
    """Mode of per-model dominant cluster per animal × tx (× phase)."""
    keys = ["animal_id", "sex", "condition", "session"]
    rows: list[dict[str, object]] = []
    for key_vals, g in per_model.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        vals = g["dominant_cluster_id"].to_numpy(dtype=np.int64)
        mode_res = stats.mode(vals, keepdims=False)
        mode_val = int(mode_res.mode) if np.ndim(mode_res.mode) == 0 else int(mode_res.mode[0])
        n_agree = int(np.sum(vals == mode_val))
        rows.append(
            {
                **key_map,
                "dominant_cluster_id": mode_val,
                "n_models": int(g["model"].nunique()),
                "n_models_agree_mode": n_agree,
                "frac_models_agree_mode": float(n_agree / len(vals)) if len(vals) else float("nan"),
                "median_n_clusters_used": float(g["n_clusters_used"].median()),
                "median_bout_frames": float(g["n_bout_frames"].median()),
            }
        )
    return pd.DataFrame(rows)


def consensus_composition_long(frames_long: pd.DataFrame) -> pd.DataFrame:
    """Median frame counts across models, normalized to fractions per animal cell."""
    keys = ["animal_id", "sex", "condition", "session", "cluster_id"]
    med = (
        frames_long.groupby(keys, as_index=False)["n_bout_frames"]
        .median()
        .rename(columns={"n_bout_frames": "median_n_bout_frames"})
    )
    cell_keys = ["animal_id", "sex", "condition", "session"]
    totals = med.groupby(cell_keys, as_index=False)["median_n_bout_frames"].sum().rename(
        columns={"median_n_bout_frames": "total_frames"}
    )
    out = med.merge(totals, on=cell_keys, how="left")
    out["frac_frames"] = out["median_n_bout_frames"] / out["total_frames"].replace(0, np.nan)
    out["n_models"] = int(frames_long["model"].nunique())
    return out


def composition_fingerprint_key(
    counts: Mapping[int, float],
    *,
    top_k: int = DEFAULT_TOP_K,
    n_bins: int = DEFAULT_FRAC_BINS,
) -> str:
    """Coarse top-k cluster composition label for discrete INFO."""
    total = float(sum(counts.values()))
    if total <= 0:
        return "empty"
    items = sorted(((int(cid), float(w) / total) for cid, w in counts.items()), key=lambda x: (-x[1], x[0]))[
        :top_k
    ]
    parts: list[str] = []
    for cid, frac in items:
        b = min(n_bins - 1, int(frac * n_bins))
        parts.append(f"{cid}:{b}")
    while len(parts) < top_k:
        parts.append("-:0")
    return "|".join(parts)


def composition_consensus_wide(comp_long: pd.DataFrame) -> pd.DataFrame:
    """One row per animal cell with fingerprint + top-cluster fractions."""
    rows: list[dict[str, object]] = []
    keys = ["animal_id", "sex", "condition", "session"]
    for key_vals, g in comp_long.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        counts = dict(zip(g["cluster_id"].astype(int), g["median_n_bout_frames"].astype(float)))
        fp = composition_fingerprint_key(counts)
        row: dict[str, object] = {
            **key_map,
            "composition_key": fp,
            "n_clusters_used": int(len(counts)),
            "total_frames": float(sum(counts.values())),
            "shannon_bits": float(
                -sum((w / sum(counts.values())) * np.log2(w / sum(counts.values())) for w in counts.values() if w > 0)
            )
            if counts
            else float("nan"),
        }
        for cid, w in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            col = f"frac_c{int(cid)}"
            row[col] = float(w / sum(counts.values())) if sum(counts.values()) > 0 else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def build_frame_tables(
    art_root: Path,
    *,
    sig_dir: Path | None = None,
    models: Sequence[str] | None = None,
    pool_phases: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sig = sig_dir or default_sig_dir(art_root)
    model_list = list(models) if models is not None else list_paramscan_models(art_root)
    frame_parts: list[pd.DataFrame] = []
    for i, model in enumerate(model_list, start=1):
        print(f"  cluster frames [{i}/{len(model_list)}] {model}", flush=True)
        long = model_cluster_frames_long(art_root, model, sig_dir=sig, pool_phases=pool_phases)
        if long.empty:
            continue
        frame_parts.append(long)
    if not frame_parts:
        raise FileNotFoundError("no per-model cluster frame rows")
    frames_long = pd.concat(frame_parts, ignore_index=True)
    dom_keys = ["model", "animal_id", "sex", "condition", "session"]
    dom_rows: list[dict[str, object]] = []
    for key_vals, g in frames_long.groupby(dom_keys, sort=True):
        key_map = dict(zip(dom_keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        counts = dict(zip(g["cluster_id"].astype(int), g["n_bout_frames"].astype(float)))
        dom_rows.append(
            {
                **key_map,
                "dominant_cluster_id": _dominant_from_acc(counts),
                "n_clusters_used": int(len(counts)),
                "n_bout_frames": float(sum(counts.values())),
            }
        )
    per_model_dom = pd.DataFrame(dom_rows)
    consensus_dom = consensus_dominant_clusters(per_model_dom)
    comp_long = consensus_composition_long(frames_long)
    comp_wide = composition_consensus_wide(comp_long)
    return frames_long, per_model_dom, consensus_dom, comp_wide


def build_cluster_table(
    art_root: Path,
    *,
    sig_dir: Path | None = None,
    models: Sequence[str] | None = None,
    pool_phases: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    _frames, per_model, consensus, _comp = build_frame_tables(
        art_root, sig_dir=sig_dir, models=models, pool_phases=pool_phases
    )
    return per_model, consensus


def perm_p_sex_y(
    sex: np.ndarray,
    y: np.ndarray,
    *,
    observed_mm: float,
    n_perm: int,
    rng: np.random.Generator,
) -> tuple[float, float]:
    if not np.isfinite(observed_mm):
        return float("nan"), float("nan")
    sex = np.asarray(sex, dtype=np.int64)
    y = np.asarray(y, dtype=np.int64)
    if sex.size < MIN_N_FOR_INFO:
        return float("nan"), float("nan")
    null = np.empty(n_perm, dtype=np.float64)
    for i in range(n_perm):
        perm_sex = rng.permutation(sex)
        _, mi_mm, _, _, _ = pair_mi_mm(perm_sex, y)
        null[i] = mi_mm
    null_mean = float(np.nanmean(null))
    p = float((np.sum(null >= observed_mm) + 1) / (n_perm + 1))
    return null_mean, p


perm_p_sex_cluster = perm_p_sex_y


def _encode_composition_keys(keys: pd.Series) -> np.ndarray:
    codes, _ = pd.factorize(keys.astype(str), sort=True)
    return codes.astype(np.int64)


def info_sex_y_cell(
    g: pd.DataFrame,
    *,
    y_col: str,
    y_kind: str,
    n_perm: int,
    rng: np.random.Generator,
) -> dict[str, object]:
    """One tx (× phase) INFO cell: X=sex, Y categorical."""
    sex = g["sex"].map(SEX_CODE).to_numpy(dtype=np.int64)
    if y_kind == "composition_key":
        y = _encode_composition_keys(g[y_col])
    else:
        y = g[y_col].to_numpy(dtype=np.int64)
    ok = np.isfinite(sex.astype(np.float64)) & np.isfinite(y.astype(np.float64))
    sex = sex[ok]
    y = y[ok]
    n = int(sex.size)
    if n < MIN_N_FOR_INFO:
        return {
            "n": n,
            "n_female": int((sex == 0).sum()) if n else 0,
            "n_male": int((sex == 1).sum()) if n else 0,
            "n_y_types": 0,
            "h_sex_bits": float("nan"),
            "h_y_bits": float("nan"),
            "mi_raw_bits": float("nan"),
            "mi_mm_bits": float("nan"),
            "null_perm_mean_bits": float("nan"),
            "perm_p": float("nan"),
            "hit_p05": False,
            "y_degenerate": True,
        }

    mi_raw, mi_mm, h_sex, h_y, _ = pair_mi_mm(sex, y)
    null_mean, perm_p = perm_p_sex_y(sex, y, observed_mm=mi_mm, n_perm=n_perm, rng=rng)
    n_y_types = int(len(np.unique(y)))
    y_degenerate = n_y_types <= 1
    return {
        "n": n,
        "n_female": int((sex == 0).sum()),
        "n_male": int((sex == 1).sum()),
        "n_y_types": n_y_types,
        "h_sex_bits": h_sex,
        "h_y_bits": h_y,
        "mi_raw_bits": mi_raw,
        "mi_mm_bits": mi_mm,
        "null_perm_mean_bits": null_mean,
        "perm_p": perm_p,
        "hit_p05": bool(np.isfinite(perm_p) and perm_p < 0.05),
        "y_degenerate": y_degenerate,
    }


def info_sex_cluster_cell(g: pd.DataFrame, *, n_perm: int, rng: np.random.Generator) -> dict[str, object]:
    rec = info_sex_y_cell(
        g,
        y_col="dominant_cluster_id",
        y_kind="dominant_cluster_id",
        n_perm=n_perm,
        rng=rng,
    )
    rec["n_clusters"] = rec.pop("n_y_types")
    rec["h_cluster_bits"] = rec.pop("h_y_bits")
    return rec


def info_sex_composition_cell(g: pd.DataFrame, *, n_perm: int, rng: np.random.Generator) -> dict[str, object]:
    rec = info_sex_y_cell(
        g,
        y_col="composition_key",
        y_kind="composition_key",
        n_perm=n_perm,
        rng=rng,
    )
    rec["n_composition_types"] = rec.pop("n_y_types")
    rec["h_composition_bits"] = rec.pop("h_y_bits")
    return rec


def run_info_lattice(
    table: pd.DataFrame,
    *,
    n_perm: int = DEFAULT_N_PERM,
    seed: int = 0,
    phases_pooled: bool = True,
    y_metric: str = "dominant_cluster_id",
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    sub = table if phases_pooled else table[table["session"] != "ALL_SESSIONS"]
    phase_values = ["ALL_SESSIONS"] if phases_pooled else list(SESSIONS)
    cell_fn = info_sex_composition_cell if y_metric == "composition_key" else info_sex_cluster_cell
    question = QUESTION_COMPOSITION if y_metric == "composition_key" else QUESTION_DOMINANT
    for condition in CONDITION_ORDER:
        for phase in phase_values:
            g = sub[(sub["condition"] == condition) & (sub["session"] == phase)]
            rec = cell_fn(g, n_perm=n_perm, rng=rng)
            rows.append(
                {
                    "condition": condition,
                    "session": phase,
                    "x_metric": "sex",
                    "y_metric": y_metric,
                    "question": question,
                    "grain": "animal × tx; cluster pooled across phases on nvl_obj"
                    if phases_pooled
                    else "animal × tx × phase; nvl_obj",
                    "design": "between_animal_association",
                    "top_k": DEFAULT_TOP_K if y_metric == "composition_key" else "",
                    "frac_bins": DEFAULT_FRAC_BINS if y_metric == "composition_key" else "",
                    **rec,
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = apply_bh(out, p_col="perm_p", q_col="q_bh")
    out["hit_fdr05"] = out["q_bh"] < 0.05
    return out


def run_info_lattice_by_phase(table: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    y_metric = str(kwargs.pop("y_metric", "dominant_cluster_id"))
    return run_info_lattice(table, phases_pooled=False, y_metric=y_metric, **kwargs)  # type: ignore[arg-type]


def write_run(
    *,
    art_root: Path,
    out_dir: Path,
    n_perm: int = DEFAULT_N_PERM,
    seed: int = 0,
    sig_dir: Path | None = None,
    skip_frame_build: bool = False,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_path = out_dir / "cluster_frames_per_model.csv"
    if skip_frame_build and frames_path.exists():
        print("loading cached cluster_frames_per_model.csv ...", flush=True)
        frames_long = pd.read_csv(frames_path)
        per_model = pd.read_csv(out_dir / "dominant_cluster_per_model.csv")
        consensus = pd.read_csv(out_dir / "dominant_cluster_consensus.csv")
        comp_long = pd.read_csv(out_dir / "cluster_composition_consensus_long.csv")
        comp_wide = pd.read_csv(out_dir / "cluster_composition_consensus.csv")
    else:
        print("building per-model cluster frame tables ...", flush=True)
        frames_long, per_model, consensus, comp_wide = build_frame_tables(art_root, sig_dir=sig_dir)
        comp_long = consensus_composition_long(frames_long)
        frames_long.to_csv(frames_path, index=False)
        per_model.to_csv(out_dir / "dominant_cluster_per_model.csv", index=False)
        consensus.to_csv(out_dir / "dominant_cluster_consensus.csv", index=False)
        comp_long.to_csv(out_dir / "cluster_composition_consensus_long.csv", index=False)
        comp_wide.to_csv(out_dir / "cluster_composition_consensus.csv", index=False)

    pooled_dom = run_info_lattice(consensus, n_perm=n_perm, seed=seed, phases_pooled=True, y_metric="dominant_cluster_id")
    pooled_dom.to_csv(out_dir / "info_sex_cluster_tests_pooled_phases.csv", index=False)

    by_phase_dom = run_info_lattice_by_phase(
        consensus, n_perm=n_perm, seed=seed + 1, y_metric="dominant_cluster_id"
    )
    by_phase_dom.to_csv(out_dir / "info_sex_cluster_tests_by_phase.csv", index=False)

    pooled_comp = run_info_lattice(
        comp_wide, n_perm=n_perm, seed=seed + 2, phases_pooled=True, y_metric="composition_key"
    )
    pooled_comp.to_csv(out_dir / "info_sex_composition_tests_pooled_phases.csv", index=False)

    by_phase_comp = run_info_lattice_by_phase(
        comp_wide, n_perm=n_perm, seed=seed + 3, y_metric="composition_key"
    )
    by_phase_comp.to_csv(out_dir / "info_sex_composition_tests_by_phase.csv", index=False)

    summary = {
        "art_root": str(art_root),
        "out_dir": str(out_dir),
        "n_perm": int(n_perm),
        "seed": int(seed),
        "n_models": int(frames_long["model"].nunique()),
        "n_consensus_rows": int(len(consensus)),
        "composition_top_k": DEFAULT_TOP_K,
        "composition_frac_bins": DEFAULT_FRAC_BINS,
        "pooled_dominant": pooled_dom.to_dict(orient="records"),
        "pooled_composition": pooled_comp.to_dict(orient="records"),
        "by_phase_dominant": by_phase_dom.to_dict(orient="records"),
        "by_phase_composition": by_phase_comp.to_dict(orient="records"),
        "n_hit_pooled_dom_p05": int(pooled_dom["hit_p05"].sum()) if len(pooled_dom) else 0,
        "n_hit_pooled_comp_p05": int(pooled_comp["hit_p05"].sum()) if len(pooled_comp) else 0,
        "n_hit_by_phase_comp_p05": int(by_phase_comp["hit_p05"].sum()) if len(by_phase_comp) else 0,
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "INFO_sex_cluster.md").write_text(
        f"""# INFO — sex vs cluster (within tx, nvl_obj)

**Questions:**
1. I(sex; dominant cluster) — mode cluster id (phases pooled).
2. I(sex; composition) — top-{DEFAULT_TOP_K} cluster fractions binned ({DEFAULT_FRAC_BINS} bins).

Ensemble: median frame counts across kpMS models, then normalize.
Permutation: shuffle sex within tx, n_perm={n_perm}.

| File | Content |
|------|---------|
| `info_sex_cluster_tests_pooled_phases.csv` | dominant cluster, phases pooled |
| `info_sex_composition_tests_pooled_phases.csv` | full composition fingerprint |
| `info_sex_composition_tests_by_phase.csv` | composition per phase × tx |
| `cluster_composition_consensus.csv` | animal composition wide + fingerprint |
""",
        encoding="utf-8",
    )
    return summary
