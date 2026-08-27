"""Bout-level sticky Gaussian HMM — portable logic (PROTOTYPE).

Question: does a bout-sequence HMM produce behavior epochs that feel more coherent
than mapping each raw syllable through prototype HDBSCAN clusters?

No I/O beyond explicit loaders; safe to lift into library code if validated.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

FEATURE_NAMES_KIN = ("speed_mps", "abs_dheading", "log_bout_frames")
FEATURE_NAMES_FULL = FEATURE_NAMES_KIN + ("syllable_norm",)


@dataclass(frozen=True)
class BoutRow:
    stream: str
    seed: str
    trial_key: str
    raw_syllable_id: int
    bout_index: int
    row_start: int
    row_end: int
    bout_frames: int
    bout_mean_speed_mps: float
    bout_mean_abs_dheading: float
    bout_frac_still: float
    bout_primary_state: str


@dataclass
class BoutTrialSequence:
    bouts: list[BoutRow]
    features: np.ndarray  # (T, D) z-scored
    feature_names: tuple[str, ...]
    cluster_ids: np.ndarray  # (T,) prototype cluster per bout; -1 if unknown
    syllable_ids: np.ndarray  # (T,)


@dataclass
class StickyGaussianHMM:
    n_states: int
    pi: np.ndarray
    transition: np.ndarray
    means: np.ndarray
    var: np.ndarray

    @property
    def n_features(self) -> int:
        return int(self.means.shape[1])


def load_trial_bouts(
    manifest_csv: Path,
    *,
    stream: str,
    seed: str,
    trial_key: str,
) -> list[BoutRow]:
    rows: list[BoutRow] = []
    with manifest_csv.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            if raw["stream"] != stream or raw["seed"] != seed or raw["trial_key"] != trial_key:
                continue
            rows.append(
                BoutRow(
                    stream=raw["stream"],
                    seed=raw["seed"],
                    trial_key=raw["trial_key"],
                    raw_syllable_id=int(raw["raw_syllable_id"]),
                    bout_index=int(raw["bout_index"]),
                    row_start=int(raw["row_start"]),
                    row_end=int(raw["row_end"]),
                    bout_frames=int(raw["bout_frames"]),
                    bout_mean_speed_mps=float(raw["bout_mean_speed_mps"]),
                    bout_mean_abs_dheading=float(raw["bout_mean_abs_dheading"]),
                    bout_frac_still=float(raw["bout_frac_still"]),
                    bout_primary_state=raw["bout_primary_state"],
                )
            )
    rows.sort(key=lambda b: b.row_start)
    return rows


def load_cluster_lookup(
    prototype_csv: Path,
    *,
    stream: str,
    seed: str,
) -> dict[int, int]:
    lookup: dict[int, int] = {}
    with prototype_csv.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            if raw["stream"] != stream or raw["seed"] != seed:
                continue
            lookup[int(raw["raw_syllable_id"])] = int(raw["cluster_id"])
    return lookup


def build_trial_sequence(
    bouts: list[BoutRow],
    *,
    cluster_lookup: dict[int, int] | None,
    include_syllable: bool,
) -> BoutTrialSequence:
    if not bouts:
        raise ValueError("empty bout list")

    syllable_ids = np.array([b.raw_syllable_id for b in bouts], dtype=np.int64)
    syl_max = max(1, int(syllable_ids.max()))
    kin = np.column_stack(
        [
            [b.bout_mean_speed_mps for b in bouts],
            [b.bout_mean_abs_dheading for b in bouts],
            [np.log1p(b.bout_frames) for b in bouts],
        ]
    )
    if include_syllable:
        kin = np.column_stack([kin, syllable_ids.astype(np.float64) / float(syl_max)])

    mu = kin.mean(axis=0)
    sigma = kin.std(axis=0)
    sigma[sigma < 1e-8] = 1.0
    features = (kin - mu) / sigma

    cluster_ids = np.array(
        [cluster_lookup.get(int(s), -1) if cluster_lookup else -1 for s in syllable_ids],
        dtype=np.int64,
    )
    names = FEATURE_NAMES_FULL if include_syllable else FEATURE_NAMES_KIN
    return BoutTrialSequence(
        bouts=bouts,
        features=features,
        feature_names=names,
        cluster_ids=cluster_ids,
        syllable_ids=syllable_ids,
    )


def sticky_transition_matrix(n_states: int, kappa: float) -> np.ndarray:
    """Row-stochastic matrix; larger kappa → longer state runs."""
    k = max(2, n_states)
    kappa = max(1.0, float(kappa))
    off = 1.0 / (k + kappa - 1.0)
    mat = np.full((k, k), off, dtype=np.float64)
    np.fill_diagonal(mat, kappa / (kappa + k - 1.0))
    mat /= mat.sum(axis=1, keepdims=True)
    return mat


def apply_stickiness(transition: np.ndarray, kappa: float) -> np.ndarray:
    kappa = max(1.0, float(kappa))
    sticky = transition.copy()
    diag = np.clip(np.diag(sticky), 1e-12, None)
    np.fill_diagonal(sticky, diag * kappa)
    sticky /= sticky.sum(axis=1, keepdims=True)
    return sticky


def _log_gaussian_diag(x: np.ndarray, means: np.ndarray, var: np.ndarray) -> np.ndarray:
    """Log emission probability; x (T,D), means/var (K,D) → (T,K)."""
    var = np.clip(var, 1e-6, None)
    diff = x[:, None, :] - means[None, :, :]
    log_det = np.sum(np.log(2.0 * np.pi * var), axis=1)
    quad = np.sum((diff * diff) / var[None, :, :], axis=2)
    return -0.5 * (log_det[None, :] + quad)


def _forward_backward(
    obs: np.ndarray, model: StickyGaussianHMM
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    log_b = _log_gaussian_diag(obs, model.means, model.var)
    t_len, k = log_b.shape
    log_a = np.log(np.clip(model.transition, 1e-300, None))
    log_pi = np.log(np.clip(model.pi, 1e-300, None))

    alpha = np.zeros((t_len, k), dtype=np.float64)
    alpha[0] = log_pi + log_b[0]
    for t in range(1, t_len):
        alpha[t] = log_b[t] + np.logaddexp.reduce(alpha[t - 1][:, None] + log_a, axis=0)

    beta = np.zeros((t_len, k), dtype=np.float64)
    for t in range(t_len - 2, -1, -1):
        beta[t] = np.logaddexp.reduce(log_a + log_b[t + 1] + beta[t + 1], axis=1)

    loglik = float(np.logaddexp.reduce(alpha[-1]))
    gamma = np.exp(alpha + beta - loglik)
    gamma /= gamma.sum(axis=1, keepdims=True)

    xi = np.zeros((t_len - 1, k, k), dtype=np.float64)
    for t in range(t_len - 1):
        num = (
            np.exp(alpha[t][:, None] + log_a + log_b[t + 1] + beta[t + 1])
            - loglik
        )
        xi[t] = num / np.clip(num.sum(), 1e-300, None)

    return gamma, xi, log_b, loglik


def viterbi(obs: np.ndarray, model: StickyGaussianHMM) -> np.ndarray:
    log_b = _log_gaussian_diag(obs, model.means, model.var)
    t_len, k = log_b.shape
    log_a = np.log(np.clip(model.transition, 1e-300, None))
    log_pi = np.log(np.clip(model.pi, 1e-300, None))

    dp = np.zeros((t_len, k), dtype=np.float64)
    back = np.zeros((t_len, k), dtype=np.int64)
    dp[0] = log_pi + log_b[0]
    for t in range(1, t_len):
        scores = dp[t - 1][:, None] + log_a
        back[t] = np.argmax(scores, axis=0)
        dp[t] = log_b[t] + np.max(scores, axis=0)

    path = np.zeros(t_len, dtype=np.int64)
    path[-1] = int(np.argmax(dp[-1]))
    for t in range(t_len - 2, -1, -1):
        path[t] = back[t + 1, path[t + 1]]
    return path


def fit_sticky_hmm(
    obs: np.ndarray,
    *,
    n_states: int,
    kappa: float,
    n_iter: int = 40,
    seed: int = 0,
) -> tuple[StickyGaussianHMM, np.ndarray, float]:
    rng = np.random.default_rng(seed)
    t_len, dim = obs.shape
    k = max(2, min(n_states, t_len))

    # K-means-lite init on observations.
    pick = rng.choice(t_len, size=k, replace=False)
    means = obs[pick].copy()
    labels = np.argmin(np.linalg.norm(obs[:, None, :] - means[None, :, :], axis=2), axis=1)
    var = np.zeros((k, dim), dtype=np.float64)
    for s in range(k):
        pts = obs[labels == s]
        var[s] = np.var(pts, axis=0) + 1e-3 if pts.size else np.ones(dim)
        if not np.any(labels == s):
            means[s] = obs[rng.integers(0, t_len)]

    pi = np.full(k, 1.0 / k)
    transition = sticky_transition_matrix(k, kappa)
    model = StickyGaussianHMM(n_states=k, pi=pi, transition=transition, means=means, var=var)

    last_path = np.zeros(t_len, dtype=np.int64)
    loglik = float("-inf")
    for _ in range(n_iter):
        gamma, xi, _, loglik = _forward_backward(obs, model)
        last_path = np.argmax(gamma, axis=1)

        pi = gamma[0] / gamma[0].sum()
        transition = xi.sum(axis=0)
        transition /= np.clip(transition.sum(axis=1, keepdims=True), 1e-300, None)
        transition = apply_stickiness(transition, kappa)

        means = (gamma.T @ obs) / np.clip(gamma.sum(axis=0), 1e-300, None)[:, None]
        diff = obs[:, None, :] - means[None, :, :]
        var = np.sum(gamma[:, :, None] * diff * diff, axis=0) / np.clip(
            gamma.sum(axis=0), 1e-300, None
        )[:, None]
        var = np.squeeze(var, axis=-1) if var.ndim == 3 else var
        var = np.clip(var, 1e-3, None)

        model = StickyGaussianHMM(
            n_states=k, pi=pi, transition=transition, means=means, var=var
        )

    decoded = viterbi(obs, model)
    _, _, _, final_ll = _forward_backward(obs, model)
    return model, decoded, final_ll


def boundary_count(labels: np.ndarray) -> int:
    if labels.size < 2:
        return 0
    return int(np.sum(labels[1:] != labels[:-1]))


def state_mean_speed(bouts: list[BoutRow], states: np.ndarray) -> dict[int, float]:
    out: dict[int, list[float]] = {}
    for bout, state in zip(bouts, states, strict=True):
        out.setdefault(int(state), []).append(bout.bout_mean_speed_mps)
    return {k: float(np.mean(v)) for k, v in out.items()}


def agreement_at_boundaries(a: np.ndarray, b: np.ndarray) -> tuple[int, int, int]:
    """Precision/recall style: do label boundaries coincide?"""
    if a.size < 2 or b.size < 2:
        return 0, 0, 0
    ba = set(np.flatnonzero(a[1:] != a[:-1]) + 1)
    bb = set(np.flatnonzero(b[1:] != b[:-1]) + 1)
    tp = len(ba & bb)
    prec = tp / len(ba) if ba else 0.0
    rec = tp / len(bb) if bb else 0.0
    return tp, int(round(prec * len(ba)) if ba else 0), int(round(rec * len(bb)) if bb else 0)


def summarize_decode(
    seq: BoutTrialSequence,
    hmm_states: np.ndarray,
) -> dict[str, object]:
    tp, _, _ = agreement_at_boundaries(hmm_states, seq.cluster_ids)
    n_hmm_bnd = boundary_count(hmm_states)
    n_cluster_bnd = boundary_count(seq.cluster_ids)
    n_syll_bnd = boundary_count(seq.syllable_ids)
    return {
        "n_bouts": len(seq.bouts),
        "n_unique_syllables": len(set(seq.syllable_ids.tolist())),
        "n_unique_clusters": len({c for c in seq.cluster_ids.tolist() if c >= 0}),
        "n_hmm_states_used": len(set(hmm_states.tolist())),
        "boundaries_syllable": n_syll_bnd,
        "boundaries_cluster": n_cluster_bnd,
        "boundaries_hmm": n_hmm_bnd,
        "boundary_coincide_hmm_cluster": tp,
        "hmm_state_mean_speed_mps": state_mean_speed(seq.bouts, hmm_states),
    }
