"""Pause-syllable occupancy MI vs binned object proximity (original MI design).

Within animal × phase × ``novel_obj`` bout stream:

    I(pause_bout; stim_bin)

where ``pause_bout`` is binary (mapped cluster-13 id) and ``stim_bin`` is the shared
5-quantile bout-mean distance bin (``dist_fam`` / ``dist_nvl``). Circular-shift
null matches ``compute_mi.py``. Companion: full-alphabet occupancy MI on the same bouts.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from maze.kpms.behavior_ethogram.stimulus_mi import assign_bins

from nor_object_mi.compute_mi import (
    STIM_VARS,
    _FIELD,
    _null_circ_mean_p,
    _pooled_occupancy,
    _streams_for_animal,
    edges_from_json,
    fit_shared_dist_bin_edges,
)
from nor_object_mi.info_dr_pause_delta import get_y_metric_spec, load_pause_y, spearman_pair
from nor_object_mi.simpler_first_object_prox import PHASES as PHASE_TAGS
from nor_object_mi.simpler_first_protocol_prologue import pearson_pair

StimVar = str


def _read_bin_edges(path: Path | None, rows: list[dict[str, object]], *, n_bins: int) -> tuple[np.ndarray, dict[str, object]]:
    if path is not None and path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        edges = edges_from_json(payload)
        return edges, payload
    edges, payload = fit_shared_dist_bin_edges(rows, n_bins=n_bins)
    return edges, payload


def _streams_pause_binary(
    rows: Sequence[Mapping[str, object]],
    *,
    animal_id: str,
    field: str,
    edges: np.ndarray,
    pause_id: int,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    by_trial: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if str(row["animal_id"]) != animal_id:
            continue
        if str(row.get("condition_layer", "")) != "novel_obj":
            continue
        val = float(row[field])
        if not np.isfinite(val):
            continue
        by_trial[str(row["trial_key"])].append(row)

    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for trial, trows in by_trial.items():
        trows = sorted(trows, key=lambda r: int(r["bout_index"]))
        pause = np.asarray(
            [1 if int(r["raw_syllable_id"]) == int(pause_id) else 0 for r in trows],
            dtype=np.int64,
        )
        stim_vals = np.asarray([float(r[field]) for r in trows], dtype=np.float64)
        stim_bin = assign_bins(stim_vals, edges)
        out[trial] = (pause, stim_bin)
    return out


def _mi_row(
    *,
    aid: str,
    meta: Mapping[str, object],
    stim: StimVar,
    label: str,
    streams: dict[str, tuple[np.ndarray, np.ndarray]],
    n_perm: int,
    rng: np.random.Generator,
) -> dict[str, object] | None:
    if not streams:
        return None
    mi_raw, mi_mm, h_label, h_stim, n_bouts = _pooled_occupancy(streams)
    if n_bouts == 0:
        return None
    null_mean, null_p = _null_circ_mean_p(streams, observed_mm=mi_mm, n_perm=n_perm, rng=rng)
    labels = np.concatenate([s[0] for s in streams.values()])
    frac_pos = float(np.mean(labels == 1)) if labels.size else float("nan")
    return {
        "animal_id": aid,
        "sex": meta["sex"],
        "tx": meta["tx"],
        "phase_layer": meta["phase_layer"],
        "stim_var": stim,
        "mi_label": label,
        "n_bouts": n_bouts,
        "H_stim": h_stim,
        "H_label": h_label,
        "mi_raw": mi_raw,
        "mi_mm": mi_mm,
        "null_circ_mean": null_mean,
        "null_circ_p": null_p,
        "excess": float(mi_mm - null_mean),
        "frac_pause_bouts": frac_pos if label == "pause_binary" else float("nan"),
    }


def compute_pause_and_full_mi(
    rows: list[dict[str, object]],
    *,
    pause_id: int,
    n_bins: int = 5,
    n_perm: int = 200,
    seed: int = 42,
    bin_edges_payload: Mapping[str, object] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Return pause_mi, full_mi, bin_edges_json."""
    if bin_edges_payload is None:
        shared_edges, bin_edges_payload = fit_shared_dist_bin_edges(rows, n_bins=n_bins)
    else:
        shared_edges = edges_from_json(bin_edges_payload)

    animals = sorted({str(r["animal_id"]) for r in rows})
    meta_by_animal: dict[str, Mapping[str, object]] = {}
    for r in rows:
        meta_by_animal.setdefault(str(r["animal_id"]), r)

    rng = np.random.default_rng(seed)
    pause_rows: list[dict[str, object]] = []
    full_rows: list[dict[str, object]] = []

    for aid in animals:
        meta = meta_by_animal[aid]
        for stim in STIM_VARS:
            field = _FIELD[stim]
            pause_streams = _streams_pause_binary(
                rows, animal_id=aid, field=field, edges=shared_edges, pause_id=pause_id
            )
            full_streams = _streams_for_animal(rows, animal_id=aid, stim=stim, edges=shared_edges)  # type: ignore[arg-type]

            pr = _mi_row(
                aid=aid,
                meta=meta,
                stim=stim,
                label="pause_binary",
                streams=pause_streams,
                n_perm=n_perm,
                rng=rng,
            )
            if pr is not None:
                pause_rows.append(pr)
            fr = _mi_row(
                aid=aid,
                meta=meta,
                stim=stim,
                label="full_alphabet",
                streams=full_streams,
                n_perm=n_perm,
                rng=rng,
            )
            if fr is not None:
                full_rows.append(fr)

    pause_df = pd.DataFrame(pause_rows)
    full_df = pd.DataFrame(full_rows)
    return pause_df, full_df, dict(bin_edges_payload)


def delta_excess(mi: pd.DataFrame) -> pd.DataFrame:
    """Novelty contrast excess_I(nvl) - excess_I(fam) per animal × mi_label."""
    need = {"animal_id", "sex", "tx", "phase_layer", "stim_var", "mi_label", "excess"}
    missing = need - set(mi.columns)
    if missing:
        raise ValueError(f"delta_excess missing columns: {sorted(missing)}")
    rows: list[dict[str, object]] = []
    keys = ["animal_id", "sex", "tx", "phase_layer", "mi_label"]
    for key_vals, g in mi.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        fam = g[g["stim_var"] == "dist_fam"]
        nvl = g[g["stim_var"] == "dist_nvl"]
        if len(fam) != 1 or len(nvl) != 1:
            continue
        rows.append(
            {
                **key_map,
                "excess_fam": float(fam["excess"].iloc[0]),
                "excess_nvl": float(nvl["excess"].iloc[0]),
                "delta_excess": float(nvl["excess"].iloc[0]) - float(fam["excess"].iloc[0]),
                "mi_mm_fam": float(fam["mi_mm"].iloc[0]),
                "mi_mm_nvl": float(nvl["mi_mm"].iloc[0]),
                "frac_pause_bouts": float(fam["frac_pause_bouts"].iloc[0])
                if "frac_pause_bouts" in fam.columns and key_map["mi_label"] == "pause_binary"
                else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def find_bout_csv(art_root: Path, model: str, tag: str) -> Path | None:
    for base in (art_root / model, art_root / "archive" / model):
        path = base / tag / "ladder_bout_features.csv"
        if path.exists():
            return path
    return None


def find_bin_edges(art_root: Path, model: str, tag: str) -> Path | None:
    for base in (art_root / model, art_root / "archive" / model):
        path = base / tag / "bin_edges.json"
        if path.exists():
            return path
    return None


def load_bout_rows(path: Path) -> list[dict[str, object]]:
    df = pd.read_csv(path)
    return df.to_dict(orient="records")


def pause_id_for_model(da_dir: Path, model: str) -> int:
    ids = pd.read_csv(da_dir / "duration_band_vs_da.csv", usecols=["model", "raw_syllable_id"])
    sub = ids[ids["model"] == model]
    if len(sub) != 1:
        raise ValueError(f"expected one mapped pause id for {model}, got {len(sub)}")
    return int(sub.iloc[0]["raw_syllable_id"])


def join_pause_mi_composition(
    delta: pd.DataFrame,
    comp: pd.DataFrame,
    *,
    y_col: str,
) -> pd.DataFrame:
    keys = ["animal_id", "sex", "tx", "phase_layer"]
    comp_sub = comp[keys + [y_col]].copy()
    delta = delta.copy()
    delta["animal_id"] = delta["animal_id"].astype(str)
    comp_sub["animal_id"] = comp_sub["animal_id"].astype(str)
    out = delta.merge(comp_sub, on=keys, how="inner")
    return out.sort_values(keys).reset_index(drop=True)


def association_table(joined: pd.DataFrame, *, y_col: str) -> pd.DataFrame:
    """Spearman / Pearson between pause MI scalars and composition Y by sex × phase."""
    rows: list[dict[str, object]] = []
    for (phase, sex, label), g in joined.groupby(["phase_layer", "sex", "mi_label"], sort=True):
        for x_col, x_name in (
            ("delta_excess", "delta_excess"),
            ("excess_nvl", "excess_nvl"),
            ("mi_mm_nvl", "mi_mm_nvl"),
        ):
            sp = spearman_pair(g[x_col].to_numpy(), g[y_col].to_numpy())
            pr = pearson_pair(g[x_col].to_numpy(), g[y_col].to_numpy())
            rows.append(
                {
                    "phase_layer": phase,
                    "sex": sex,
                    "mi_label": label,
                    "x_metric": x_name,
                    "y_metric": y_col,
                    "n": int(len(g)),
                    "spearman_rho": sp["spearman_rho"],
                    "spearman_p": sp["p"],
                    "pearson_r": pr["pearson_r"],
                    "pearson_p": pr["p"],
                }
            )
    return pd.DataFrame(rows)


DEFAULT_MODEL = "paramscan_s1-1e8_s2-1e5_ss-50"
DEFAULT_N_BINS = 5
DEFAULT_N_PERM = 200


def default_out_dir(art_root: Path, model: str) -> Path:
    return art_root / f"simpler_first_pause_stim_mi__{model}"


def info_md(*, model: str, pause_id: int, n_bins: int, n_perm: int) -> str:
    return f"""# Pause syllable occupancy MI vs binned object proximity

**Claim:** within animal × phase on `novel_obj` bouts, compare

- `I(pause_binary; stim_bin)` — cluster-13 mapped id {pause_id} in model `{model}`
- `I(full_alphabet; stim_bin)` — original pilot occupancy MI

`stim_bin` = shared {n_bins}-quantile bout-mean spot→object distance (`dist_fam` / `dist_nvl`).
Novelty contrast: `delta_excess = excess_I(dist_nvl) − excess_I(dist_fam)`.
Circular-shift null, n_perm={n_perm}.

**Bridge to composition:** Spearman between per-animal pause MI scalars and
median cluster-13 `p_novel` / `delta_p_novelty` (21-model DA merge) — same animal×phase
grain as INFO runs, but X is bout-level MI not object-prox DR.

Not library code — scratch pilot only.
"""


def compare_archived_full_mi(
    delta: pd.DataFrame,
    archived_path: Path,
    *,
    phase_layer: str = "NOR_TX",
) -> pd.DataFrame:
    """Litmus: full-alphabet delta_excess vs archived mi_per_animal.csv (one phase)."""
    if not archived_path.exists():
        return pd.DataFrame()
    arch = pd.read_csv(archived_path)
    arch["animal_id"] = arch["animal_id"].astype(str)
    arch = arch[(arch["phase_layer"] == phase_layer) & (arch["mi_type"] == "occupancy")].copy()
    fam = arch[arch["stim_var"] == "dist_fam"].set_index("animal_id")["excess"]
    nvl = arch[arch["stim_var"] == "dist_nvl"].set_index("animal_id")["excess"]
    arch_delta = (nvl - fam).rename("archived_delta_excess")
    ours = delta[(delta["phase_layer"] == phase_layer) & (delta["mi_label"] == "full_alphabet")].copy()
    ours["animal_id"] = ours["animal_id"].astype(str)
    ours = ours.set_index("animal_id")["delta_excess"]
    joined = pd.concat([ours.rename("recomputed_delta_excess"), arch_delta], axis=1, join="inner")
    joined.index = joined.index.astype(str)
    if joined.empty:
        return joined.reset_index()
    joined["abs_diff"] = (joined["recomputed_delta_excess"] - joined["archived_delta_excess"]).abs()
    return joined.reset_index()


def write_run(
    *,
    art_root: Path,
    da_dir: Path,
    out_dir: Path,
    model: str = DEFAULT_MODEL,
    n_bins: int = DEFAULT_N_BINS,
    n_perm: int = DEFAULT_N_PERM,
    seed: int = 42,
    y_metrics: Sequence[str] = ("p_novel", "delta_p_novelty"),
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pause_id = pause_id_for_model(da_dir, model)

    pause_parts: list[pd.DataFrame] = []
    full_parts: list[pd.DataFrame] = []
    phase_tags: list[dict[str, str]] = []
    bin_payload: dict[str, object] = {}

    for phase_layer, tag in PHASE_TAGS:
        bout_path = find_bout_csv(art_root, model, tag)
        if bout_path is None:
            phase_tags.append({"phase_layer": phase_layer, "tag": tag, "bout_csv": "", "status": "missing"})
            continue
        rows = load_bout_rows(bout_path)
        edges_path = find_bin_edges(art_root, model, tag)
        payload = None
        if edges_path is not None:
            payload = json.loads(edges_path.read_text(encoding="utf-8"))
        pause_df, full_df, bin_payload = compute_pause_and_full_mi(
            rows,
            pause_id=pause_id,
            n_bins=n_bins,
            n_perm=n_perm,
            seed=seed,
            bin_edges_payload=payload,
        )
        pause_parts.append(pause_df)
        full_parts.append(full_df)
        phase_tags.append(
            {"phase_layer": phase_layer, "tag": tag, "bout_csv": str(bout_path), "status": "ok"}
        )

    if not pause_parts:
        raise FileNotFoundError(f"no bout CSVs found for model {model} under {art_root}")

    pause_long = pd.concat(pause_parts, ignore_index=True)
    full_long = pd.concat(full_parts, ignore_index=True)
    pause_long.to_csv(out_dir / "pause_mi_long.csv", index=False)
    full_long.to_csv(out_dir / "full_mi_long.csv", index=False)

    delta = delta_excess(pd.concat([pause_long, full_long], ignore_index=True))
    delta.to_csv(out_dir / "pause_stim_delta_excess.csv", index=False)

    (out_dir / "bin_edges.json").write_text(json.dumps(bin_payload, indent=2), encoding="utf-8")

    archived = art_root / "archive" / model / "mi_per_animal.csv"
    litmus = compare_archived_full_mi(delta, archived)
    if not litmus.empty:
        litmus.to_csv(out_dir / "litmus_full_alphabet_tx.csv", index=False)

    assoc_frames: list[pd.DataFrame] = []
    join_paths: dict[str, str] = {}
    for y_token in y_metrics:
        spec = get_y_metric_spec(y_token)
        comp = load_pause_y(da_dir, spec)
        joined = join_pause_mi_composition(delta, comp, y_col=spec.y_col)
        fname = f"joined_pause_mi_vs_{spec.token}.csv"
        joined.to_csv(out_dir / fname, index=False)
        join_paths[spec.token] = fname
        assoc = association_table(joined, y_col=spec.y_col)
        assoc["y_metric_token"] = spec.token
        assoc_frames.append(assoc)

    assoc_all = pd.concat(assoc_frames, ignore_index=True)
    assoc_all.to_csv(out_dir / "association_tests_long.csv", index=False)

    (out_dir / "INFO_pause_stim_mi.md").write_text(
        info_md(model=model, pause_id=pause_id, n_bins=n_bins, n_perm=n_perm),
        encoding="utf-8",
    )

    summary: dict[str, object] = {
        "art_root": str(art_root),
        "da_dir": str(da_dir),
        "out_dir": str(out_dir),
        "model": model,
        "pause_id": pause_id,
        "n_bins": n_bins,
        "n_perm": n_perm,
        "seed": seed,
        "y_metrics": list(y_metrics),
        "phase_tags": phase_tags,
        "n_pause_rows": int(len(pause_long)),
        "n_delta_rows": int(len(delta)),
        "join_files": join_paths,
    }
    if not litmus.empty:
        summary["litmus_tx_max_abs_diff"] = float(litmus["abs_diff"].max())
        summary["litmus_tx_n"] = int(len(litmus))
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
