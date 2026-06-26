"""Stage III bout AR-HMM fit and decode (jax_moseq.models.arhmm)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .arhmm_config import BoutArhmmConfig
from .bout_scalars import BoutScalarFeatures, feature_matrix_for_arhmm
from .cluster import zscore_features


@dataclass(frozen=True)
class TrialBoutSequence:
    trial_key: str
    seed: str
    features: np.ndarray
    rows: tuple[BoutScalarFeatures, ...]


@dataclass(frozen=True)
class BatchedBoutData:
    x: np.ndarray
    mask: np.ndarray
    trial_keys: tuple[str, ...]
    seeds: tuple[str, ...]
    bout_counts: tuple[int, ...]


@dataclass(frozen=True)
class BoutArhmmFitResult:
    model: dict
    scaled: BatchedBoutData
    feature_mean: np.ndarray
    feature_std: np.ndarray


def batch_trial_bout_sequences(
    sequences: Sequence[TrialBoutSequence],
) -> BatchedBoutData:
    if not sequences:
        raise ValueError("sequences must be non-empty")
    d = int(sequences[0].features.shape[1])
    max_bouts = max(seq.features.shape[0] for seq in sequences)
    n = len(sequences)
    x = np.zeros((n, max_bouts, d), dtype=np.float64)
    mask = np.zeros((n, max_bouts), dtype=np.float64)
    counts: list[int] = []
    keys: list[str] = []
    seeds: list[str] = []
    for i, seq in enumerate(sequences):
        t = int(seq.features.shape[0])
        if seq.features.shape[1] != d:
            raise ValueError("all trials must share feature dimension")
        x[i, :t, :] = seq.features
        mask[i, :t] = 1.0
        counts.append(t)
        keys.append(seq.trial_key)
        seeds.append(seq.seed)
    return BatchedBoutData(
        x=x,
        mask=mask,
        trial_keys=tuple(keys),
        seeds=tuple(seeds),
        bout_counts=tuple(counts),
    )


def zscore_batched_features(
    batched: BatchedBoutData,
) -> tuple[BatchedBoutData, np.ndarray, np.ndarray]:
    """Column-wise z-score on masked bout rows (same convention as Stage II HDBSCAN)."""
    mask = batched.mask > 0
    if not np.any(mask):
        raise ValueError("bout batch has no valid rows")
    flat = batched.x[mask]
    zflat, mean, std = zscore_features(flat)
    x = batched.x.copy()
    x[mask] = zflat
    return (
        BatchedBoutData(
            x=x,
            mask=batched.mask,
            trial_keys=batched.trial_keys,
            seeds=batched.seeds,
            bout_counts=batched.bout_counts,
        ),
        mean,
        std,
    )


def build_trial_sequences_from_table(
    table_rows: Sequence[dict[str, str]],
    *,
    include_heading_direction: bool = False,
    include_cluster_feature: bool = False,
) -> list[TrialBoutSequence]:
    from .bout_table_io import dict_to_bout_scalar_features

    by_trial: dict[tuple[str, str], list[tuple[int, dict[str, str], BoutScalarFeatures]]] = {}
    for row in table_rows:
        key = (str(row["seed"]), str(row["trial_key"]))
        feat = dict_to_bout_scalar_features(row)
        by_trial.setdefault(key, []).append((int(row["bout_index"]), row, feat))

    sequences: list[TrialBoutSequence] = []
    for (seed, trial_key), items in sorted(by_trial.items()):
        items.sort(key=lambda t: t[0])
        feats = [t[2] for t in items]
        cluster_ids = [int(t[1]["cluster_id"]) if str(t[1].get("cluster_id", "")).strip() else -1 for t in items]
        mat, _ = feature_matrix_for_arhmm(
            feats,
            include_heading_direction=include_heading_direction,
            include_cluster_feature=include_cluster_feature,
            cluster_ids=cluster_ids if include_cluster_feature else None,
        )
        sequences.append(
            TrialBoutSequence(
                trial_key=trial_key,
                seed=seed,
                features=mat,
                rows=tuple(feats),
            )
        )
    return sequences


def fit_bout_arhmm(
    batched: BatchedBoutData,
    cfg: BoutArhmmConfig,
) -> BoutArhmmFitResult:
    from jax import config as jax_config
    from jax_moseq.models.arhmm import init_hyperparams, init_model, resample_model

    scaled, mean, std = zscore_batched_features(batched)
    jax_config.update("jax_enable_x64", True)
    data = {"x": scaled.x.astype(np.float64), "mask": scaled.mask.astype(np.float64)}
    hp = init_hyperparams(
        cfg.trans_hypparams(),
        cfg.ar_hypparams(scaled.x.shape[-1]),
    )
    model = init_model(
        data=data,
        hypparams=hp,
        seed=np.array([0, int(cfg.seed)], dtype=np.uint32),
    )
    for _ in range(int(cfg.num_iters)):
        model = resample_model(data, **model, verbose=False)
    return BoutArhmmFitResult(model=model, scaled=scaled, feature_mean=mean, feature_std=std)


def decode_behavior_tokens(
    model: dict,
    batched: BatchedBoutData,
    *,
    nlags: int,
) -> list[tuple[str, str, list[int]]]:
    """Map AR-HMM ``z`` to one token per bout (pad first ``nlags`` bouts with first inferred state)."""
    z = np.asarray(model["states"]["z"])
    nlags = max(0, int(nlags))
    out: list[tuple[str, str, list[int]]] = []
    for i, n_bouts in enumerate(batched.bout_counts):
        n_infer = max(0, int(n_bouts) - nlags)
        z_row = [int(x) for x in z[i, :n_infer].tolist()]
        if not z_row:
            tokens = [0] * int(n_bouts)
        else:
            tokens = [z_row[0]] * nlags + z_row
            if len(tokens) < int(n_bouts):
                tokens.extend([z_row[-1]] * (int(n_bouts) - len(tokens)))
            tokens = tokens[: int(n_bouts)]
        out.append((batched.seeds[i], batched.trial_keys[i], tokens))
    return out


def count_unique_behavior_tokens(decoded: Sequence[tuple[str, str, list[int]]]) -> int:
    return len({int(t) for _s, _k, toks in decoded for t in toks})
