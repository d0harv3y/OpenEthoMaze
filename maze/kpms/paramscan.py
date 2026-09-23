"""kpMS param-scan grid helpers (NOR-compatible naming + VAST conf sweep)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterator

# NOR param-scan stage-2 κ and alphabet size (K).
# Middle value is the log-decade midpoint 10**4.5 (≈31622.78), folder-labeled ``3e4``.
NOR_STAGE2_KAPPA: tuple[float, ...] = (1e4, 10**4.5, 1e5)
NOR_NUM_STATES: tuple[int, ...] = (50, 75, 100)

# VAST extension: confidence mask during preprocess + init_model.
VAST_CONF_THRESHOLDS: tuple[float, ...] = (0.1, 0.2, 0.3)

# Fixed stage-1 stickiness for this sweep (NOR paramscan often used 1e8).
DEFAULT_STAGE1_KAPPA: float = 1e8

# Per-animal NOR full-protocol sweep: hold stage-1 κ, single conf, 3×3 = 9 models.
NOR_PER_ANIMAL_STAGE1_KAPPA: float = 1e7
NOR_PER_ANIMAL_CONF_THRESHOLD: float = 0.2


def kappa_token(kappa: float) -> str:
    """Format stickiness for model dir tokens (``1e4``, ``3e4``, ``1e8``, …).

    Matches legacy ``sci(..., sig_digits=0)`` naming: the log-midpoint
    ``10**(n+0.5)`` (mantissa ≈ √10) labels as ``3e{n}``, same as literal ``3e4``.
    """
    if kappa <= 0:
        raise ValueError(f"kappa must be positive, got {kappa}")
    exp = int(round(math.log10(kappa)))
    mantissa = kappa / (10.0**exp)
    if abs(mantissa - 1.0) < 1e-3:
        return f"1e{exp}"
    if abs(mantissa - 3.0) < 0.05 or abs(mantissa - math.sqrt(10.0)) < 0.05:
        return f"3e{exp}"
    return f"{kappa:g}"


def conf_token(conf: float) -> str:
    """Format confidence threshold for model dir tokens."""
    return f"{conf:g}"


def paramscan_model_name(
    *,
    stage1_kappa: float = DEFAULT_STAGE1_KAPPA,
    stage2_kappa: float,
    num_states: int,
    conf_threshold: float,
) -> str:
    """Return ``paramscan_s1-*_s2-*_ss-*_ct-*`` model directory name."""
    return (
        f"paramscan_s1-{kappa_token(stage1_kappa)}"
        f"_s2-{kappa_token(stage2_kappa)}"
        f"_ss-{num_states}"
        f"_ct-{conf_token(conf_threshold)}"
    )


@dataclass(frozen=True)
class ParamscanJob:
    """One hyperparameter combo in a param-scan sweep."""

    stage1_kappa: float
    stage2_kappa: float
    num_states: int
    conf_threshold: float

    @property
    def model_name(self) -> str:
        return paramscan_model_name(
            stage1_kappa=self.stage1_kappa,
            stage2_kappa=self.stage2_kappa,
            num_states=self.num_states,
            conf_threshold=self.conf_threshold,
        )


def iter_vast_conf_paramscan_grid(
    *,
    stage1_kappa: float = DEFAULT_STAGE1_KAPPA,
    stage2_values: tuple[float, ...] = NOR_STAGE2_KAPPA,
    num_states_values: tuple[int, ...] = NOR_NUM_STATES,
    conf_thresholds: tuple[float, ...] = VAST_CONF_THRESHOLDS,
) -> Iterator[ParamscanJob]:
    """Cartesian product s2 × ss × conf (default 3×3×3 = 27 jobs)."""
    for stage2_kappa in stage2_values:
        for num_states in num_states_values:
            for conf_threshold in conf_thresholds:
                yield ParamscanJob(
                    stage1_kappa=stage1_kappa,
                    stage2_kappa=stage2_kappa,
                    num_states=num_states,
                    conf_threshold=conf_threshold,
                )


def iter_nor_per_animal_paramscan_grid(
    *,
    stage1_kappa: float = NOR_PER_ANIMAL_STAGE1_KAPPA,
    stage2_values: tuple[float, ...] = NOR_STAGE2_KAPPA,
    num_states_values: tuple[int, ...] = NOR_NUM_STATES,
    conf_threshold: float = NOR_PER_ANIMAL_CONF_THRESHOLD,
) -> Iterator[ParamscanJob]:
    """NOR per-animal grid: fixed stage1 κ + conf → s2 × ss (default 9 jobs)."""
    yield from iter_vast_conf_paramscan_grid(
        stage1_kappa=stage1_kappa,
        stage2_values=stage2_values,
        num_states_values=num_states_values,
        conf_thresholds=(conf_threshold,),
    )


def animal_paramscan_model_name(animal_id: str, job: ParamscanJob) -> str:
    """``{animal_id}_paramscan_s1-*_s2-*_ss-*_ct-*`` leaf model directory name."""
    return f"{animal_id}_{job.model_name}"
