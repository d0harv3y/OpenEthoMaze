"""ProxComp — syllable composition in exclusive 0.10 m object-prox disks.

Grain: animal × session × nvl_obj. Exclusive fam / nvl balls (dual-gated
frames dropped). Composition DR cousins + clock-portable ``dr_time_prox``.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from nor_object_mi.quad_comp import composition_scalars, dr_cousin, shannon_bits

FAMILY_METRICS: tuple[str, ...] = ("dr_shannon_prox", "dr_richness_prox")
FAMILY_SEXES: tuple[str, ...] = ("F", "M")
# Per-scalar BH families (declared 2026-10-08): one family per DR cousin, m=2 (F,M).
PER_SCALAR_FAMILY_METRICS: tuple[str, ...] = (
    "dr_shannon_prox",
    "dr_richness_prox",
    "dr_hill2_prox",
)
PER_SCALAR_FAMILY_NAME: dict[str, str] = {
    "dr_shannon_prox": "ProxComp-Shannon",
    "dr_richness_prox": "ProxComp-Richness",
    "dr_hill2_prox": "ProxComp-Hill2",
}
PER_SCALAR_FAMILY_SIZE: int = len(FAMILY_SEXES)  # cells per scalar family
LEVEL_FAMILY_METRICS: tuple[str, ...] = (
    "fam_shannon_prox",
    "nvl_shannon_prox",
    "fam_richness_prox",
    "nvl_richness_prox",
)
TIME_FAMILY_METRICS: tuple[str, ...] = ("dr_time_prox",)
FAMILY_A_SIZE: int = len(FAMILY_METRICS) * len(FAMILY_SEXES)
LEVEL_FAMILY_A_SIZE: int = len(LEVEL_FAMILY_METRICS) * len(FAMILY_SEXES)
TIME_FAMILY_A_SIZE: int = len(TIME_FAMILY_METRICS) * len(FAMILY_SEXES)
FAMILY_SESSIONS_PANEL: tuple[str, ...] = (
    "NOR_BL",
    "NOR_TX",
    "NOR_REC3hr",
    "NOR_REC11hr",
)
LITMUS_T1_ASSAY_SESSION = "NOR_TX"
LITMUS_T1_ASSAY_CONDITION = "noSD"
# Legacy aliases (pre theory-indexed litmus names)
LITMUS_A_SESSION = LITMUS_T1_ASSAY_SESSION
LITMUS_A_CONDITION = LITMUS_T1_ASSAY_CONDITION
TRIAL = "nvl_obj"
MIN_FRAMES_N = 10
NEAR_R_M = 0.10
GRAIN = "animal x {session} x nvl_obj x exclusive_prox_r=0.10m (cluster_id)"
NOISE_CLUSTER = -1

# re-export for tests that expect shannon on this module
assert shannon_bits is not None


def score_prox_composition(
    d_fam_m: np.ndarray,
    d_nvl_m: np.ndarray,
    valid: np.ndarray,
    syll_cluster: np.ndarray,
    *,
    r_m: float = NEAR_R_M,
    min_frames: int = MIN_FRAMES_N,
) -> dict[str, float | bool | int]:
    """Exclusive circular prox composition + time DR."""
    d_f = np.asarray(d_fam_m, dtype=np.float64)
    d_n = np.asarray(d_nvl_m, dtype=np.float64)
    ok = np.asarray(valid, dtype=bool) & np.isfinite(d_f) & np.isfinite(d_n)
    lab = np.asarray(syll_cluster, dtype=np.int64).ravel()
    n = int(min(ok.shape[0], lab.shape[0], d_f.shape[0], d_n.shape[0]))
    d_f, d_n, ok, lab = d_f[:n], d_n[:n], ok[:n], lab[:n]
    r = float(r_m)

    near_fam = ok & (d_f < r)
    near_nvl = ok & (d_n < r)
    both = near_fam & near_nvl
    fam_only = near_fam & ~both
    nvl_only = near_nvl & ~both

    n_spot_fam = float(np.sum(fam_only))
    n_spot_nvl = float(np.sum(nvl_only))
    n_spot_both = float(np.sum(both))
    time_eligible = n_spot_fam >= float(min_frames) and n_spot_nvl >= float(min_frames)
    dr_time = dr_cousin(n_spot_nvl, n_spot_fam) if time_eligible else float("nan")

    mapped = ok & (lab != NOISE_CLUSTER)
    fam_m = mapped & fam_only
    nvl_m = mapped & nvl_only
    fam_s = composition_scalars(lab[fam_m])
    nvl_s = composition_scalars(lab[nvl_m])
    eligible = (
        fam_s["n_frames"] >= float(min_frames) and nvl_s["n_frames"] >= float(min_frames)
    )
    d_h = float(nvl_s["shannon_bits"] - fam_s["shannon_bits"]) if eligible else float("nan")
    d_r = float(nvl_s["richness"] - fam_s["richness"]) if eligible else float("nan")
    d_hill = float(nvl_s["hill2_eff"] - fam_s["hill2_eff"]) if eligible else float("nan")
    dr_h = dr_cousin(nvl_s["shannon_bits"], fam_s["shannon_bits"]) if eligible else float("nan")
    dr_r = dr_cousin(nvl_s["richness"], fam_s["richness"]) if eligible else float("nan")
    dr_hill = (
        dr_cousin(nvl_s["hill2_eff"], fam_s["hill2_eff"]) if eligible else float("nan")
    )

    return {
        "n_frames_fam_prox": float(fam_s["n_frames"]),
        "n_frames_nvl_prox": float(nvl_s["n_frames"]),
        "n_spot_fam_prox": n_spot_fam,
        "n_spot_nvl_prox": n_spot_nvl,
        "n_spot_both_prox": n_spot_both,
        "richness_fam_prox": float(fam_s["richness"]),
        "richness_nvl_prox": float(nvl_s["richness"]),
        "fam_richness_prox": float(fam_s["richness"]),
        "nvl_richness_prox": float(nvl_s["richness"]),
        "shannon_bits_fam_prox": float(fam_s["shannon_bits"]),
        "shannon_bits_nvl_prox": float(nvl_s["shannon_bits"]),
        "fam_shannon_prox": float(fam_s["shannon_bits"]),
        "nvl_shannon_prox": float(nvl_s["shannon_bits"]),
        "delta_shannon_prox": d_h,
        "dr_shannon_prox": dr_h,
        "delta_richness_prox": d_r,
        "dr_richness_prox": dr_r,
        "fam_hill2_prox": float(fam_s["hill2_eff"]),
        "nvl_hill2_prox": float(nvl_s["hill2_eff"]),
        "delta_hill2_prox": d_hill,
        "dr_hill2_prox": dr_hill,
        "dr_time_prox": dr_time,
        "time_contrast_eligible": bool(time_eligible),
        "contrast_eligible": bool(eligible),
        "n_valid_spot": int(np.sum(ok)),
        "n_mapped_syll": int(np.sum(mapped)),
        "r_m": float(r),
        "min_frames_n": int(min_frames),
    }


def assert_family_a_size(n_finite_p: int) -> None:
    if int(n_finite_p) != FAMILY_A_SIZE:
        raise AssertionError(
            f"Family ProxComp-A expects {FAMILY_A_SIZE} finite-p cells, got {n_finite_p}"
        )


def assert_per_scalar_family_sizes(tests_by_metric: Mapping[str, int]) -> None:
    for metric in PER_SCALAR_FAMILY_METRICS:
        n = int(tests_by_metric.get(metric, -1))
        if n != PER_SCALAR_FAMILY_SIZE:
            raise AssertionError(
                f"Family {PER_SCALAR_FAMILY_NAME[metric]} expects "
                f"{PER_SCALAR_FAMILY_SIZE} finite-p cells, got {n} for {metric}"
            )


def assert_time_family_a_size(n_finite_p: int) -> None:
    if int(n_finite_p) != TIME_FAMILY_A_SIZE:
        raise AssertionError(
            f"Family TimeProx-A expects {TIME_FAMILY_A_SIZE} finite-p cells, got {n_finite_p}"
        )


def assert_level_family_a_size(n_finite_p: int) -> None:
    if int(n_finite_p) != LEVEL_FAMILY_A_SIZE:
        raise AssertionError(
            f"Family ProxLevel-A expects {LEVEL_FAMILY_A_SIZE} finite-p cells, got {n_finite_p}"
        )


def row_in_family_a(row: Mapping[str, object]) -> bool:
    return (
        str(row.get("session", "")) == LITMUS_A_SESSION
        and str(row.get("sex", "")) in FAMILY_SEXES
        and str(row.get("metric", "")) in FAMILY_METRICS
        and str(row.get("trial", TRIAL)) == TRIAL
        and str(row.get("family", "ProxComp-A")) == "ProxComp-A"
    )
