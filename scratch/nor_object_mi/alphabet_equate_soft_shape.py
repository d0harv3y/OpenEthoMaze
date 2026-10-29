"""Cheap alphabet-equating poke: shape-of-bout + accent residualize + soft NN.

(0) Soft equate diagnostics (leave-animal-out 1-NN / 5-NN) instead of only HDBSCAN.
(1) Shape-of-bout scalars alongside the classic 9 mean/IQR kinematics.

Runs the same protocol on pooled ``moseq_251017`` and per-animal
``nor_per_animal_paramscan``. Aggregates bout rows to
``(animal_id, model, raw_syllable_id)`` prototypes online (no 4 GB CSV rewrite).

Regen (OpenEthoMaze repo root, PowerShell):

  uv run python scratch/nor_object_mi/alphabet_equate_soft_shape.py --layout pooled --clean
  uv run python scratch/nor_object_mi/alphabet_equate_soft_shape.py --layout per_animal --clean
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Sequence

import h5py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from maze.kpms.behavior_ethogram.cluster import zscore_features  # noqa: E402
from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_DOUBLE,
    INK,
    apply_style,
    fig_footnote,
    save_pdf_svg,
    type_scale,
)
from maze.kpms.behavior_ethogram.bout_kinematics import (  # noqa: E402
    abs_dheading_per_frame,
)
from maze.kpms.behavior_ethogram.bout_scalars import (  # noqa: E402
    bout_iqr,
    bout_net_dheading_rad,
    bout_straightness,
    syllable_runs,
)
from nor_object_mi.bout_kinematics import (  # noqa: E402
    CONDITIONS,
    SESSIONS,
    SHAPE_FIELDS,
    bout_shape_scalars,
    discover_paramscan_models,
    discover_per_animal_paramscan_models,
    model_num_states,
    nose_tail_length_m,
    session_fps,
    spot_speed_mps,
    spot_step_length_m,
)
from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402
from nor_object_mi.ngram_decisions import DEFAULT_MIN_BOUT_FRAMES_CLEAN  # noqa: E402
from nor_object_mi.spot_xy import spot_xy_m  # noqa: E402
from nor_object_mi.syllable_cleanup import maybe_absorb_short_bouts  # noqa: E402

DEFAULT_NOR = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_POOLED = Path(r"D:\sack\datas\impress\moseq_251017")
DEFAULT_PER_ANIMAL = Path(r"D:\sack\datas\impress\nor_per_animal_paramscan")

BASELINE_BOUT_COLS: tuple[str, ...] = (
    "bout_mean_speed_mps",
    "bout_mean_abs_dheading",
    "bout_mean_nose_tail_m",
    "bout_iqr_speed_mps",
    "bout_iqr_abs_dheading",
    "bout_iqr_nose_tail_m",
    "bout_duration_s",
    "bout_net_dheading_rad",
    "bout_straightness",
)

ACCENT_COLS: tuple[str, ...] = (
    "bout_mean_nose_tail_m",
    "bout_iqr_nose_tail_m",
)

# Include session + trial so Plotly strata filters can gate protocol steps.
# ``trial`` = object step (nvl_obj / id_obj / no_obj); not prose “phase”.
PROTO_KEY: tuple[str, ...] = (
    "animal_id",
    "model",
    "raw_syllable_id",
    "session",
    "trial",
)
MIN_BOUTS_DEFAULT = 3
PROGRESS_EVERY_S = 45.0


def _out_dir(ensemble_root: Path) -> Path:
    return ensemble_root / "_nor_object_mi" / "alphabet_equate_soft_shape"


def residualize_within_animal(
    df: pd.DataFrame,
    cols: Sequence[str],
    *,
    animal_col: str = "animal_id",
) -> pd.DataFrame:
    """Subtract within-animal median for accent-ish columns (level, not delta)."""
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            continue
        med = out.groupby(animal_col, dropna=False)[c].transform("median")
        out[c] = out[c] - med
    return out


def paramscan_stem(model: str) -> str:
    """Strip leading ``{animal}_`` so per-animal fits share a hyperparam stem.

    ``3115_paramscan_s1-…`` → ``paramscan_s1-…``. Pooled names already start
    with ``paramscan_`` and are returned unchanged.
    """
    s = str(model)
    if "_paramscan_" in s:
        return "paramscan_" + s.split("_paramscan_", 1)[1]
    return s


def _weighted_mean_frame(
    df: pd.DataFrame,
    gcols: Sequence[str],
    feature_cols: Sequence[str],
    *,
    weight_col: str = "n_bouts",
) -> pd.DataFrame:
    """Bout-weighted mean of features within groups; sum weights (vectorized)."""
    feats = [c for c in feature_cols if c in df.columns]
    work = df[list(gcols) + feats + [weight_col] + (
        ["animal_id"] if "animal_id" in df.columns and "animal_id" not in gcols else []
    )].copy()
    w = work[weight_col].to_numpy(dtype=np.float64)
    w = np.where(np.isfinite(w) & (w > 0), w, 0.0)
    work[weight_col] = w
    for c in feats:
        x = work[c].to_numpy(dtype=np.float64)
        num = np.where(np.isfinite(x), x * w, 0.0)
        # zero weight where feature non-finite so denominator matches
        work[f"_num_{c}"] = num
        work[f"_den_{c}"] = np.where(np.isfinite(x), w, 0.0)

    gb = work.groupby(list(gcols), dropna=False, sort=True)
    out = gb[weight_col].sum().rename(weight_col).to_frame()
    for c in feats:
        num = gb[f"_num_{c}"].sum()
        den = gb[f"_den_{c}"].sum().replace(0.0, np.nan)
        out[c] = num / den
    if "animal_id" in work.columns and "animal_id" not in gcols:
        out["n_animals_in_group"] = gb["animal_id"].nunique()
    return out.reset_index()


def average_over_animals(
    proto: pd.DataFrame,
    feature_cols: Sequence[str],
    *,
    layout: str,
    min_bouts: int = MIN_BOUTS_DEFAULT,
) -> pd.DataFrame:
    """Collapse animal (and session/trial) → one row per alphabet × syllable.

    **pooled:** group ``(model, raw_syllable_id)`` — same grain as syllable
    signatures (~50s HDBSCAN islands).

    **per_animal:** group ``(paramscan_stem, raw_syllable_id)`` across animals.
    Integer ids are **not** portable (ADR-0005); this is an exploratory foil to
    ask whether kinematic islands still appear after averaging mismatched
    alphabets.

    Session/trial are collapsed **within animal** first (bout-weighted), then
    ``min_bouts`` is applied on that animal×model×syllable total — otherwise
    per-session gates wipe rare syllables before the cross-animal average.
    """
    df = proto.copy()
    feats = [c for c in feature_cols if c in df.columns]

    # 1) Within animal: drop session/trial
    within_key = ["animal_id", "model", "raw_syllable_id"]
    if "ss" in df.columns:
        within_key = ["animal_id", "model", "ss", "raw_syllable_id"]
    if "session" in df.columns or "trial" in df.columns:
        df = _weighted_mean_frame(df, within_key, feats, weight_col="n_bouts")
    if int(min_bouts) > 1 and "n_bouts" in df.columns:
        df = df.loc[df["n_bouts"] >= int(min_bouts)].copy()

    if layout == "pooled":
        df["alphabet"] = df["model"].astype(str)
    elif layout == "per_animal":
        df["alphabet"] = df["model"].map(paramscan_stem)
    else:
        raise ValueError(f"layout must be pooled|per_animal, got {layout!r}")

    gcols = ["alphabet", "raw_syllable_id"]
    if "ss" in df.columns:
        gcols = ["alphabet", "ss", "raw_syllable_id"]

    # 2) Across animals (bout-weighted)
    out = _weighted_mean_frame(df, gcols, feats, weight_col="n_bouts")
    out = out.rename(columns={"alphabet": "model"})
    if "n_animals_in_group" in out.columns:
        out = out.rename(columns={"n_animals_in_group": "n_animals"})
    out["animal_id"] = "avg"
    out["sex"] = ""
    out["condition"] = ""
    out["session"] = ""
    out["trial"] = ""
    out["n_member_rows"] = out.get("n_animals", pd.Series(1, index=out.index))
    return out


def pool_animal_model_syllable(
    bout_df: pd.DataFrame,
    feature_cols: Sequence[str],
    *,
    min_bouts: int,
) -> pd.DataFrame:
    """Nanmean bout features → one prototype per animal × model × syllable."""
    need = set(PROTO_KEY) | set(feature_cols)
    missing = need - set(bout_df.columns)
    if missing:
        raise KeyError(f"pool missing columns: {sorted(missing)}")
    g = bout_df.groupby(list(PROTO_KEY), dropna=False, sort=True)
    agg = {c: (c, "mean") for c in feature_cols}
    agg["n_bouts"] = ("raw_syllable_id", "size")
    if "ss" in bout_df.columns:
        agg["ss"] = ("ss", "first")
    if "sex" in bout_df.columns:
        agg["sex"] = ("sex", "first")
    if "condition" in bout_df.columns:
        agg["condition"] = ("condition", "first")
    if "cohort" in bout_df.columns:
        agg["cohort"] = ("cohort", "first")
    out = g.agg(**agg).reset_index()
    return out.loc[out["n_bouts"] >= int(min_bouts)].reset_index(drop=True)


def soft_nn_metrics(
    Z: np.ndarray,
    animal_ids: np.ndarray,
    *,
    k_neighborhood: int = 5,
) -> dict[str, float]:
    """Leave-animal-out 1-NN distance + same-animal purity of k-NN."""
    n = int(Z.shape[0])
    if n < 3:
        return {
            "n": float(n),
            "mean_5nn_dist": float("nan"),
            "mean_cross_animal_1nn_dist": float("nan"),
            "frac_5nn_same_animal": float("nan"),
        }
    k_all = min(k_neighborhood + 1, n)
    nn_all = NearestNeighbors(n_neighbors=k_all, algorithm="auto").fit(Z)
    dist_all, idx_all = nn_all.kneighbors(Z)
    # skip self at column 0
    mean_5nn = float(np.mean(dist_all[:, 1:]))

    same_fracs: list[float] = []
    for i in range(n):
        nbrs = idx_all[i, 1:]
        same = animal_ids[nbrs] == animal_ids[i]
        same_fracs.append(float(np.mean(same)) if same.size else float("nan"))

    # Brute leave-animal-out 1-NN (block by animal when feasible).
    cross_d: list[float] = []
    animals = pd.unique(animal_ids)
    if len(animals) >= 2:
        for aid in animals:
            mask_i = animal_ids == aid
            mask_o = ~mask_i
            if not mask_i.any() or not mask_o.any():
                continue
            nn = NearestNeighbors(n_neighbors=1, algorithm="auto").fit(Z[mask_o])
            d, _ = nn.kneighbors(Z[mask_i])
            cross_d.extend(d.ravel().tolist())

    return {
        "n": float(n),
        "mean_5nn_dist": mean_5nn,
        "mean_cross_animal_1nn_dist": float(np.mean(cross_d)) if cross_d else float("nan"),
        "frac_5nn_same_animal": float(np.nanmean(same_fracs)),
    }


def hdbscan_foil(Z: np.ndarray, *, min_cluster_size: int = 5, min_samples: int = 3) -> dict:
    try:
        import hdbscan
    except ImportError:
        return {"available": False, "n_clusters": None, "n_noise": None, "noise_frac": None}
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=int(min_cluster_size),
        min_samples=int(min_samples),
    )
    labels = clusterer.fit_predict(Z)
    n_noise = int(np.sum(labels < 0))
    n_clust = int(len(set(labels)) - (1 if n_noise else 0))
    return {
        "available": True,
        "n_clusters": n_clust,
        "n_noise": n_noise,
        "noise_frac": float(n_noise) / float(len(labels)) if len(labels) else float("nan"),
        "min_cluster_size": int(min_cluster_size),
        "min_samples": int(min_samples),
    }


def evaluate_feature_set(
    proto: pd.DataFrame,
    feature_cols: Sequence[str],
    *,
    tag: str,
    accent_resid: bool,
) -> tuple[dict, np.ndarray, np.ndarray, PCA]:
    df = proto.copy()
    cols = list(feature_cols)
    if accent_resid:
        df = residualize_within_animal(df, [c for c in ACCENT_COLS if c in cols])
    X = df[cols].to_numpy(dtype=np.float64)
    ok = np.isfinite(X).all(axis=1)
    df = df.loc[ok].reset_index(drop=True)
    X = X[ok]
    Z, _, _ = zscore_features(X)
    animals = df["animal_id"].astype(str).to_numpy()
    soft = soft_nn_metrics(Z, animals)
    pca = PCA(n_components=min(3, Z.shape[1], Z.shape[0])).fit(Z)
    Z_pca = pca.transform(Z)
    foil = hdbscan_foil(Z)
    summary = {
        "tag": tag,
        "accent_resid": bool(accent_resid),
        "feature_cols": cols,
        "n_prototypes": int(Z.shape[0]),
        "n_features": int(Z.shape[1]),
        "pca_var_ratio": [float(v) for v in pca.explained_variance_ratio_],
        "soft": soft,
        "hdbscan": foil,
    }
    return summary, Z_pca, animals, pca


def _plot_pca_panel(
    ax: plt.Axes,
    Z: np.ndarray,
    animals: np.ndarray,
    title: str,
    var_ratio: Sequence[float],
) -> None:
    # Color by animal hash — only to show accent islands vs mush; legend omitted.
    rng = np.random.default_rng(0)
    uniq = list(pd.unique(animals))
    colors = {a: rng.random(3) * 0.7 + 0.15 for a in uniq}
    c = np.array([colors[a] for a in animals])
    ax.scatter(Z[:, 0], Z[:, 1], c=c, s=6, alpha=0.45, linewidths=0)
    pc1 = float(var_ratio[0]) if len(var_ratio) else float("nan")
    pc2 = float(var_ratio[1]) if len(var_ratio) > 1 else float("nan")
    ax.set_xlabel(f"PC1 ({pc1:.0%})")
    ax.set_ylabel(f"PC2 ({pc2:.0%})")
    ax.set_title(title, color=INK)


def write_figures(
    out: Path,
    panels: list[tuple[str, np.ndarray, np.ndarray, Sequence[float]]],
    *,
    layout: str,
) -> None:
    apply_style()
    ts = type_scale()
    n = len(panels)
    ncols = 2
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(
        nrows, ncols, figsize=FIGSIZE_DOUBLE, squeeze=False, constrained_layout=True
    )
    for i, (title, Z, animals, vr) in enumerate(panels):
        r, c = divmod(i, ncols)
        if Z.shape[1] < 2:
            axes[r][c].set_visible(False)
            continue
        _plot_pca_panel(axes[r][c], Z, animals, title, vr)
    for j in range(n, nrows * ncols):
        r, c = divmod(j, ncols)
        axes[r][c].set_visible(False)
    fig.suptitle(
        f"Alphabet equate soft+shape — {layout} (color=animal)",
        fontsize=ts["suptitle"],
        color=INK,
    )
    fig_footnote(
        fig,
        "D only · leave-animal soft NN in run_summary.json · HDBSCAN is foil",
    )
    fig_dir = out / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    save_pdf_svg(fig, fig_dir / "fig_alphabet_equate_soft_shape_pca")


def _bout_feature_vector(
    *,
    speed_sl: np.ndarray,
    dh_sl: np.ndarray,
    nt_sl: np.ndarray,
    h_sl: np.ndarray,
    xy_sl: np.ndarray,
    step_sl: np.ndarray,
    n_frames: int,
    fps: float,
    feat_index: dict[str, int],
    n_dim: int,
) -> np.ndarray:
    """Pack baseline9 + shape scalars into a fixed feature vector."""
    vec = np.full(n_dim, np.nan, dtype=np.float64)
    fin_s = speed_sl[np.isfinite(speed_sl)]
    fin_dh = dh_sl[np.isfinite(dh_sl)]
    mean_speed = float(np.mean(fin_s)) if fin_s.size else float("nan")
    mean_dh = float(np.mean(fin_dh)) if fin_dh.size else float("nan")
    vals = {
        "bout_mean_speed_mps": mean_speed,
        "bout_mean_abs_dheading": mean_dh,
        "bout_mean_nose_tail_m": (
            float(np.nanmean(nt_sl)) if np.isfinite(nt_sl).any() else float("nan")
        ),
        "bout_iqr_speed_mps": bout_iqr(speed_sl),
        "bout_iqr_abs_dheading": bout_iqr(dh_sl),
        "bout_iqr_nose_tail_m": bout_iqr(nt_sl),
        "bout_duration_s": float(n_frames) / float(fps) if fps > 0 else float("nan"),
        "bout_net_dheading_rad": bout_net_dheading_rad(h_sl),
        "bout_straightness": bout_straightness(xy_sl),
    }
    # path length unused in feat set but step_sl kept for future
    _ = step_sl
    vals.update(bout_shape_scalars(speed_sl, dh_sl, nt_sl))
    for name, i in feat_index.items():
        if name in vals:
            vec[i] = float(vals[name])
    return vec


def _accumulate_bout_vec(
    sums: dict[tuple, np.ndarray],
    counts: dict[tuple, np.ndarray],
    n_bouts: dict[tuple, int],
    meta: dict[tuple, dict[str, object]],
    key: tuple,
    vec: np.ndarray,
    *,
    ss: float | int,
    sex: str,
    condition: str,
    cohort: str,
) -> None:
    finite = np.isfinite(vec)
    s = np.where(finite, vec, 0.0)
    c = finite.astype(np.float64)
    if key not in sums:
        sums[key] = s.copy()
        counts[key] = c.copy()
        n_bouts[key] = 1
        meta[key] = {"ss": ss, "sex": sex, "condition": condition, "cohort": cohort}
    else:
        sums[key] += s
        counts[key] += c
        n_bouts[key] += 1


def accumulate_from_h5(
    *,
    nor_h5_path: Path,
    ensemble_root: Path,
    layout: str,
    min_bout_frames: int | None,
    feature_cols: Sequence[str],
    max_models: int | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Walk models; online-sum bout features → prototypes (no bout-row materialization)."""
    sums: dict[tuple, np.ndarray] = {}
    counts: dict[tuple, np.ndarray] = {}
    n_bouts: dict[tuple, int] = {}
    meta: dict[tuple, dict[str, object]] = {}
    feats = list(feature_cols)
    feat_index = {c: i for i, c in enumerate(feats)}
    n_dim = len(feats)
    t0 = time.monotonic()
    last_progress = t0
    n_models_ok = 0
    n_bout_total = 0
    n_skip_err = 0

    with h5py.File(nor_h5_path, "r") as nor_h5:
        cohort = filter_cohort(nor_h5)
        kept = set(cohort["kept_ids"])  # type: ignore[arg-type]

        if layout == "pooled":
            models = discover_paramscan_models(ensemble_root)
            model_paths = [(m, ensemble_root / m / "results.h5") for m in models]
        elif layout == "per_animal":
            model_paths = list(discover_per_animal_paramscan_models(ensemble_root))
        else:
            raise ValueError(f"layout must be pooled|per_animal, got {layout!r}")

        if max_models is not None:
            model_paths = model_paths[: int(max_models)]

        n_models = len(model_paths)
        if n_models == 0:
            raise FileNotFoundError(f"No models under {ensemble_root} ({layout})")

        for i, (model, kpms_path) in enumerate(model_paths, start=1):
            if not kpms_path.is_file():
                print(f"[{i}/{n_models}] MISSING {model}", flush=True)
                continue
            ss = model_num_states(model)
            with h5py.File(kpms_path, "r") as kpms_h5:
                sessions = list(
                    iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=None)
                )
                for js in sessions:
                    if js.session not in SESSIONS or js.trial not in CONDITIONS:
                        continue
                    try:
                        sg = nor_h5[js.animal_id][js.raw_session]
                        kg = kpms_h5[js.kpms_key]
                        syll = maybe_absorb_short_bouts(
                            kg["syllable"][()], min_bout_frames
                        )
                        heading = np.asarray(kg["heading"][()], dtype=np.float64).ravel()
                        fps = session_fps(sg)
                        x_m, y_m, valid, _ppm = spot_xy_m(sg)
                        nose_tail, _ = nose_tail_length_m(sg)
                        speed = spot_speed_mps(x_m, y_m, valid, fps)
                        step_m = spot_step_length_m(x_m, y_m, valid)
                        n = min(
                            syll.shape[0],
                            heading.shape[0],
                            x_m.shape[0],
                            speed.shape[0],
                            nose_tail.shape[0],
                            step_m.shape[0],
                        )
                        syll = syll[:n]
                        heading = heading[:n]
                        x_m = x_m[:n]
                        y_m = y_m[:n]
                        speed = speed[:n]
                        step_m = step_m[:n]
                        nose_tail = nose_tail[:n]
                        abs_dh = abs_dheading_per_frame(heading)
                        xy = np.column_stack([x_m, y_m])
                        for _bout_i, (sid, start, end) in enumerate(syllable_runs(syll)):
                            vec = _bout_feature_vector(
                                speed_sl=speed[start:end],
                                dh_sl=abs_dh[start:end],
                                nt_sl=nose_tail[start:end],
                                h_sl=heading[start:end],
                                xy_sl=xy[start:end],
                                step_sl=step_m[start:end],
                                n_frames=int(end - start),
                                fps=fps,
                                feat_index=feat_index,
                                n_dim=n_dim,
                            )
                            key = (
                                str(js.animal_id),
                                model,
                                int(sid),
                                str(js.session),
                                str(js.trial),
                            )
                            _accumulate_bout_vec(
                                sums,
                                counts,
                                n_bouts,
                                meta,
                                key,
                                vec,
                                ss=ss,
                                sex=str(js.sex or ""),
                                condition=str(js.condition or ""),
                                cohort=str(js.cohort or ""),
                            )
                            n_bout_total += 1
                    except Exception:  # noqa: BLE001 — scratch: skip bad sessions
                        n_skip_err += 1
            n_models_ok += 1

            now = time.monotonic()
            if now - last_progress >= PROGRESS_EVERY_S or i == n_models:
                rate = i / max(now - t0, 1e-6)
                eta = (n_models - i) / max(rate, 1e-6)
                print(
                    f"[{i}/{n_models}] models_ok={n_models_ok} "
                    f"bouts={n_bout_total} prototypes={len(sums)} "
                    f"err={n_skip_err} eta_s={eta:.0f} last={model}",
                    flush=True,
                )
                last_progress = now

    rows_out: list[dict[str, object]] = []
    for key, s in sums.items():
        c = counts[key]
        with np.errstate(invalid="ignore", divide="ignore"):
            means = np.where(c > 0, s / c, np.nan)
        animal_id, model, sid, session, trial = key
        rec: dict[str, object] = {
            "animal_id": animal_id,
            "model": model,
            "raw_syllable_id": int(sid),
            "session": session,
            "trial": trial,
            "n_bouts": int(n_bouts[key]),
            **meta.get(key, {}),
        }
        for j, col in enumerate(feats):
            rec[col] = float(means[j])
        rows_out.append(rec)

    proto = pd.DataFrame(rows_out)
    summary = {
        "layout": layout,
        "ensemble_root": str(ensemble_root),
        "nor_h5": str(nor_h5_path),
        "n_models": n_models,
        "n_models_ok": n_models_ok,
        "n_bout_rows_seen": n_bout_total,
        "n_session_errors": n_skip_err,
        "n_prototypes_raw": int(len(proto)),
        "min_bout_frames": min_bout_frames,
        "include_proximity": False,
        "elapsed_s": float(time.monotonic() - t0),
    }
    return proto, summary


def _info_md(layout: str) -> str:
    return f"""# INFO — alphabet equate soft + shape ({layout})

## Question (plain)

Do shape-of-bout kinematics plus within-animal accent residualization improve
cross-animal soft matching of syllable prototypes vs the classic 9 mean/IQR
columns (and vs HDBSCAN islands)?

## Grain

`(animal_id, model, raw_syllable_id, session, trial)` prototypes,
`n_bouts` ≥ min_bouts. ``trial`` = object step; ``condition`` = SD arm.
Layout: **{layout}**.

## Feature sets

| Tag | Columns |
|-----|---------|
| baseline9 | speed / \\|dheading\\| / nose–tail mean+IQR, duration, net dh, straightness |
| baseline9_shape | baseline9 + peak/time-to-peak/accel asym/still duty/nose–tail Δ/turn p90/curvature |
| *_accent_resid | same, after subtracting within-animal median of nose–tail mean+IQR |

## Soft metrics (D)

- `mean_5nn_dist` — local density in z-scored feature space
- `mean_cross_animal_1nn_dist` — leave-animal-out 1-NN distance (lower ⇒ easier soft equate)
- `frac_5nn_same_animal` — animal purity of neighborhoods (lower after resid ⇒ less accent clump)
- HDBSCAN n_clusters / noise_frac — foil only

## What this is not

Not condition I. Not portable `raw_syllable_id`. Not a Q4/Q5 lock.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--layout",
        choices=("pooled", "per_animal"),
        required=True,
        help="pooled=moseq_251017 ensemble; per_animal=nor_per_animal_paramscan",
    )
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR)
    ap.add_argument("--ensemble-root", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--min-bouts", type=int, default=MIN_BOUTS_DEFAULT)
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--min-bout-frames", type=int, default=None)
    ap.add_argument(
        "--max-models",
        type=int,
        default=None,
        help="Debug cap on model count",
    )
    ap.add_argument(
        "--from-prototypes",
        type=Path,
        default=None,
        help="Skip H5 walk; evaluate an existing prototypes CSV",
    )
    args = ap.parse_args(argv)

    if args.ensemble_root is None:
        ensemble = DEFAULT_POOLED if args.layout == "pooled" else DEFAULT_PER_ANIMAL
    else:
        ensemble = args.ensemble_root
    out = args.out_dir or _out_dir(ensemble)
    out.mkdir(parents=True, exist_ok=True)

    if args.min_bout_frames is not None:
        min_bout = args.min_bout_frames
    elif args.clean:
        min_bout = DEFAULT_MIN_BOUT_FRAMES_CLEAN
    else:
        min_bout = None

    feat_cols = list(BASELINE_BOUT_COLS) + list(SHAPE_FIELDS)
    print(f"layout={args.layout} ensemble={ensemble}", flush=True)
    proto_path = out / "prototypes_animal_model_syllable.csv"
    if args.from_prototypes is not None:
        proto_raw = pd.read_csv(args.from_prototypes)
        walk_summary = {
            "layout": args.layout,
            "ensemble_root": str(ensemble),
            "from_prototypes": str(args.from_prototypes),
            "n_prototypes_raw": int(len(proto_raw)),
        }
    else:
        proto_raw, walk_summary = accumulate_from_h5(
            nor_h5_path=args.nor_h5,
            ensemble_root=ensemble,
            layout=args.layout,
            min_bout_frames=min_bout,
            feature_cols=feat_cols,
            max_models=args.max_models,
        )

    # Keep all session×trial cells on disk so avg_animals can collapse within
    # animal before min_bouts (rare syllables otherwise vanish).
    proto_raw.to_csv(proto_path, index=False)
    proto = proto_raw.loc[proto_raw["n_bouts"] >= int(args.min_bouts)].reset_index(
        drop=True
    )

    cells: list[tuple[str, Sequence[str], bool]] = [
        ("baseline9", BASELINE_BOUT_COLS, False),
        ("baseline9_accent_resid", BASELINE_BOUT_COLS, True),
        ("baseline9_shape", feat_cols, False),
        ("baseline9_shape_accent_resid", feat_cols, True),
    ]

    summaries: list[dict] = []
    panels: list[tuple[str, np.ndarray, np.ndarray, Sequence[float]]] = []
    for tag, cols, resid in cells:
        summary, Z_pca, animals, _pca = evaluate_feature_set(
            proto, cols, tag=tag, accent_resid=resid
        )
        summaries.append(summary)
        panels.append((tag, Z_pca, animals, summary["pca_var_ratio"]))
        soft = summary["soft"]
        print(
            f"  {tag}: n={summary['n_prototypes']} "
            f"cross1nn={soft['mean_cross_animal_1nn_dist']:.3f} "
            f"same5nn={soft['frac_5nn_same_animal']:.3f} "
            f"hdbscan_k={summary['hdbscan'].get('n_clusters')}",
            flush=True,
        )

    write_figures(out, panels, layout=args.layout)

    run = {
        **walk_summary,
        "min_bouts": int(args.min_bouts),
        "n_prototypes_kept": int(len(proto)),
        "feature_sets": summaries,
        "prototypes_csv": str(proto_path),
    }
    (out / "run_summary.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    (out / "INFO_alphabet_equate_soft_shape.md").write_text(
        _info_md(args.layout), encoding="utf-8"
    )
    print(f"Wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
