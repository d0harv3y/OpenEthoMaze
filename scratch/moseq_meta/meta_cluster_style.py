"""Shared meta-cluster lookup + join helpers (NOR + VAST)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

from nor_object_mi.fig_simpler_first_syllable_signatures import (  # noqa: E402
    NOISE_COLOR,
    build_cluster_color_lookup,
)

DEFAULT_META = Path(r"C:\Users\admin\Documents\work\sack\moseq_meta_syllable_signatures_k100_gerstner")
UNMAPPED_CLUSTER = -2
UNMAPPED_COLOR = "#c8c8c8"
EXPERIMENT_MARKER = {"nor": "o", "vast": "^"}
EXPERIMENT_COLOR = {"nor": "#0072B2", "vast": "#E69F00"}


def load_meta_clustered(meta_dir: Path = DEFAULT_META) -> pd.DataFrame:
    return pd.read_csv(meta_dir / "syllable_prototypes_meta_clustered.csv")


def load_meta_summary(meta_dir: Path = DEFAULT_META) -> pd.DataFrame:
    return pd.read_csv(meta_dir / "meta_cluster_summary.csv")


def load_meta_lookup(
    meta_dir: Path = DEFAULT_META,
) -> tuple[dict[int, tuple[float, float, float, float]], list[int], object]:
    summary = load_meta_summary(meta_dir).rename(columns={"meta_cluster_id": "cluster_id"})
    lookup, cluster_ids, listed = build_cluster_color_lookup(summary)
    lookup[UNMAPPED_CLUSTER] = mcolors.to_rgba(UNMAPPED_COLOR)
    return lookup, cluster_ids, listed


def sig_table_for_experiment(meta_dir: Path, experiment: str) -> pd.DataFrame:
    """Return model × syllable table with ``cluster_id`` = meta_cluster_id."""
    proto = load_meta_clustered(meta_dir)
    sub = proto[proto["experiment"] == experiment].copy()
    out = sub[["model", "raw_syllable_id", "meta_cluster_id"]].rename(
        columns={"meta_cluster_id": "cluster_id"}
    )
    out["cluster_id"] = pd.to_numeric(out["cluster_id"], errors="coerce").fillna(-1).astype(int)
    return out


def attach_meta_cluster(
    tests: pd.DataFrame,
    meta_dir: Path,
    experiment: str,
) -> pd.DataFrame:
    sig = sig_table_for_experiment(meta_dir, experiment)
    out = tests.merge(sig, on=["model", "raw_syllable_id"], how="left")
    cid = pd.to_numeric(out["cluster_id"], errors="coerce")
    out["cluster_id"] = cid.fillna(UNMAPPED_CLUSTER).astype(np.int64)
    return out


def load_meta_model_filter(meta_dir: Path = DEFAULT_META) -> dict[str, object]:
    """Read model subset from run_summary.json (if present)."""
    path = Path(meta_dir) / "run_summary.json"
    if not path.is_file():
        return {}
    run = json.loads(path.read_text(encoding="utf-8"))
    mf = run.get("model_filter") or {}
    return {
        "nor_ss": mf.get("nor_ss"),
        "vast_models": list(mf.get("vast_models") or []),
        "nor_models": list(run.get("nor_models_in_fit") or []),
        "all_models": bool(mf.get("all_models")),
    }


def filter_da_tests_for_meta(tests: pd.DataFrame, experiment: str, meta_dir: Path = DEFAULT_META) -> pd.DataFrame:
    mf = load_meta_model_filter(meta_dir)
    if mf.get("all_models"):
        return tests
    if experiment == "nor":
        models = mf.get("nor_models") or []
        if models:
            return tests[tests["model"].astype(str).isin(models)].copy()
    if experiment == "vast":
        models = mf.get("vast_models") or []
        if models:
            return tests[tests["model"].astype(str).isin(models)].copy()
    return tests


def clustered_for_fig(meta_dir: Path = DEFAULT_META) -> pd.DataFrame:
    """Prototype table with ``cluster_id`` alias for signature figure helpers."""
    cl = load_meta_clustered(meta_dir).copy()
    cl["cluster_id"] = pd.to_numeric(cl["meta_cluster_id"], errors="coerce").fillna(-1).astype(int)
    return cl


def summary_for_fig(meta_dir: Path = DEFAULT_META) -> pd.DataFrame:
    return load_meta_summary(meta_dir).rename(columns={"meta_cluster_id": "cluster_id"})


def highlight_meta_cluster(summary: pd.DataFrame) -> int:
    """Prefer cross-experiment slow/long blob; else max median_n_bouts among multi-model."""
    s = summary.copy()
    s["median_n_bouts"] = pd.to_numeric(s["median_n_bouts"], errors="coerce")
    s["n_experiments"] = pd.to_numeric(s["n_experiments"], errors="coerce")
    cross = s[s["n_experiments"] >= 2].copy()
    if not cross.empty:
        cross = cross.sort_values(
            ["mean_sig_speed", "mean_duration_s", "mean_straightness"],
            ascending=[True, False, True],
        )
        return int(cross.iloc[0]["cluster_id"])
    s["n_models"] = pd.to_numeric(s["n_models"], errors="coerce")
    return int(s.loc[s["median_n_bouts"].idxmax(), "cluster_id"])
