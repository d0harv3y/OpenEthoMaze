"""QuadComp — syllable composition in object-assigned arena quadrants.

Grain: animal × session × nvl_obj. After fam-left alignment, split the arena
into four equal cells about the center. ``fam_quad`` / ``nvl_quad`` are the
cells that hold each object center (diagonal placement typical). Remaining
cells pool as ``other``. Compass labels are not claim tokens.

Primary DR cousins contrast nvl_quad vs fam_quad (repertoire preference).
``other`` is panel D only (Family A sealed).
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

FAMILY_METRICS: tuple[str, ...] = ("dr_shannon_quad", "dr_richness_quad")
LEVEL_FAMILY_METRICS: tuple[str, ...] = (
    "fam_shannon_quad",
    "nvl_shannon_quad",
    "fam_richness_quad",
    "nvl_richness_quad",
)
TIME_FAMILY_METRICS: tuple[str, ...] = ("dr_time_quad",)
TIME_FAMILY_A_SIZE: int = len(TIME_FAMILY_METRICS) * len(("F", "M"))
FAMILY_SEXES: tuple[str, ...] = ("F", "M")
FAMILY_A_SIZE: int = len(FAMILY_METRICS) * len(FAMILY_SEXES)
LEVEL_FAMILY_A_SIZE: int = len(LEVEL_FAMILY_METRICS) * len(FAMILY_SEXES)
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
GRAIN = "animal x {session} x nvl_obj x fam_quad|nvl_quad|other (cluster_id)"
NOISE_CLUSTER = -1


def shannon_bits(p: np.ndarray) -> float:
    """Abundance uncertainty H = −∑ p log2 p over p > 0 (bits)."""
    q = np.asarray(p, dtype=np.float64)
    q = q[np.isfinite(q) & (q > 0)]
    if q.size == 0:
        return float("nan")
    q = q / q.sum()
    return float(-np.sum(q * np.log2(q)))


def hill2_eff(p: np.ndarray) -> float:
    """Hill q=2 effective number: 1 / ∑ p_k² (Simpson inverse)."""
    q = np.asarray(p, dtype=np.float64)
    q = q[np.isfinite(q) & (q > 0)]
    if q.size == 0:
        return float("nan")
    q = q / q.sum()
    lam = float(np.sum(q * q))
    if lam <= 0.0:
        return float("nan")
    return float(1.0 / lam)


def rotate180_xy(
    x: np.ndarray,
    y: np.ndarray,
    *,
    cx: float,
    cy: float,
) -> tuple[np.ndarray, np.ndarray]:
    return (2.0 * cx - x), (2.0 * cy - y)


def rotate180_point(pt: np.ndarray, *, cx: float, cy: float) -> np.ndarray:
    p = np.asarray(pt, dtype=np.float64).ravel()[:2]
    return np.array([2.0 * cx - p[0], 2.0 * cy - p[1]], dtype=np.float64)


def cell_key(x: float, y: float, *, cx: float, cy: float) -> tuple[int, int]:
    """Four cells by signs of (x−cx), (y−cy). On-axis uses ≥ (east / 'high-y')."""
    return (int(float(x) >= float(cx)), int(float(y) >= float(cy)))


def cell_keys_array(
    x: np.ndarray,
    y: np.ndarray,
    *,
    cx: float,
    cy: float,
) -> np.ndarray:
    """Return (n, 2) int keys for each frame."""
    xa = np.asarray(x, dtype=np.float64)
    ya = np.asarray(y, dtype=np.float64)
    out = np.column_stack(
        [
            (xa >= float(cx)).astype(np.int64),
            (ya >= float(cy)).astype(np.int64),
        ]
    )
    return out


def composition_scalars(labels: np.ndarray) -> dict[str, float]:
    """Frame-share richness + Shannon + Hill q=2 on integer labels (finite only)."""
    lab = np.asarray(labels, dtype=np.int64).ravel()
    if lab.size == 0:
        return {
            "n_frames": 0.0,
            "richness": float("nan"),
            "shannon_bits": float("nan"),
            "hill2_eff": float("nan"),
        }
    uniq, counts = np.unique(lab, return_counts=True)
    tot = float(counts.sum())
    p = counts.astype(np.float64) / tot
    return {
        "n_frames": tot,
        "richness": float(uniq.size),
        "shannon_bits": float(shannon_bits(p)),
        "hill2_eff": float(hill2_eff(p)),
    }


def dr_cousin(nvl: float, fam: float) -> float:
    """(nvl − fam) / (nvl + fam); NaN if denom ≤ 0 or non-finite."""
    a = float(nvl)
    b = float(fam)
    if not (np.isfinite(a) and np.isfinite(b)):
        return float("nan")
    denom = a + b
    if denom <= 0.0:
        return float("nan")
    return float((a - b) / denom)


def score_quad_composition(
    x_px: np.ndarray,
    y_px: np.ndarray,
    valid: np.ndarray,
    syll_cluster: np.ndarray,
    *,
    cx: float,
    cy: float,
    fam_center_px: np.ndarray,
    nvl_center_px: np.ndarray,
    rotate_180: bool,
    min_frames: int = MIN_FRAMES_N,
) -> dict[str, float | bool | int]:
    """Per-animal×session QuadComp scalars.

    ``syll_cluster`` already mapped to portable cluster_id; use ``NOISE_CLUSTER``
    (-1) for unmapped frames (excluded from compositions).
    """
    x = np.asarray(x_px, dtype=np.float64).copy()
    y = np.asarray(y_px, dtype=np.float64).copy()
    ok = np.asarray(valid, dtype=bool) & np.isfinite(x) & np.isfinite(y)
    lab = np.asarray(syll_cluster, dtype=np.int64).ravel()
    n = int(min(ok.shape[0], lab.shape[0], x.shape[0], y.shape[0]))
    x, y, ok, lab = x[:n], y[:n], ok[:n], lab[:n]

    fam_c = np.asarray(fam_center_px, dtype=np.float64).ravel()[:2].copy()
    nvl_c = np.asarray(nvl_center_px, dtype=np.float64).ravel()[:2].copy()
    if rotate_180:
        x, y = rotate180_xy(x, y, cx=cx, cy=cy)
        fam_c = rotate180_point(fam_c, cx=cx, cy=cy)
        nvl_c = rotate180_point(nvl_c, cx=cx, cy=cy)

    fam_cell = cell_key(float(fam_c[0]), float(fam_c[1]), cx=cx, cy=cy)
    nvl_cell = cell_key(float(nvl_c[0]), float(nvl_c[1]), cx=cx, cy=cy)
    collision = fam_cell == nvl_cell

    empty = {
        "n_frames_fam_quad": 0.0,
        "n_frames_nvl_quad": 0.0,
        "n_frames_other": 0.0,
        "n_spot_fam_quad": 0.0,
        "n_spot_nvl_quad": 0.0,
        "n_spot_other": 0.0,
        "richness_fam_quad": float("nan"),
        "richness_nvl_quad": float("nan"),
        "richness_other": float("nan"),
        "fam_richness_quad": float("nan"),
        "nvl_richness_quad": float("nan"),
        "shannon_bits_fam_quad": float("nan"),
        "shannon_bits_nvl_quad": float("nan"),
        "shannon_bits_other": float("nan"),
        "fam_shannon_quad": float("nan"),
        "nvl_shannon_quad": float("nan"),
        "delta_shannon_quad": float("nan"),
        "dr_shannon_quad": float("nan"),
        "delta_richness_quad": float("nan"),
        "dr_richness_quad": float("nan"),
        "fam_hill2_quad": float("nan"),
        "nvl_hill2_quad": float("nan"),
        "delta_hill2_quad": float("nan"),
        "dr_hill2_quad": float("nan"),
        "dr_time_quad": float("nan"),
        "time_contrast_eligible": False,
        "contrast_eligible": False,
        "object_cell_collision": bool(collision),
        "fam_cell_x": int(fam_cell[0]),
        "fam_cell_y": int(fam_cell[1]),
        "nvl_cell_x": int(nvl_cell[0]),
        "nvl_cell_y": int(nvl_cell[1]),
        "n_valid_spot": int(np.sum(ok)),
        "n_mapped_syll": 0,
        "rotate_180": bool(rotate_180),
        "min_frames_n": int(min_frames),
    }
    if collision or int(np.sum(ok)) == 0:
        return empty

    keys = cell_keys_array(x, y, cx=cx, cy=cy)
    fam_spot = ok & (keys[:, 0] == fam_cell[0]) & (keys[:, 1] == fam_cell[1])
    nvl_spot = ok & (keys[:, 0] == nvl_cell[0]) & (keys[:, 1] == nvl_cell[1])
    other_spot = ok & ~(
        ((keys[:, 0] == fam_cell[0]) & (keys[:, 1] == fam_cell[1]))
        | ((keys[:, 0] == nvl_cell[0]) & (keys[:, 1] == nvl_cell[1]))
    )
    n_spot_fam = float(np.sum(fam_spot))
    n_spot_nvl = float(np.sum(nvl_spot))
    n_spot_oth = float(np.sum(other_spot))
    time_eligible = n_spot_fam >= float(min_frames) and n_spot_nvl >= float(min_frames)
    dr_time = dr_cousin(n_spot_nvl, n_spot_fam) if time_eligible else float("nan")

    mapped = ok & (lab != NOISE_CLUSTER)
    fam_m = mapped & (keys[:, 0] == fam_cell[0]) & (keys[:, 1] == fam_cell[1])
    nvl_m = mapped & (keys[:, 0] == nvl_cell[0]) & (keys[:, 1] == nvl_cell[1])
    other_m = mapped & ~(
        ((keys[:, 0] == fam_cell[0]) & (keys[:, 1] == fam_cell[1]))
        | ((keys[:, 0] == nvl_cell[0]) & (keys[:, 1] == nvl_cell[1]))
    )

    fam_s = composition_scalars(lab[fam_m])
    nvl_s = composition_scalars(lab[nvl_m])
    oth_s = composition_scalars(lab[other_m])

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
        "n_frames_fam_quad": float(fam_s["n_frames"]),
        "n_frames_nvl_quad": float(nvl_s["n_frames"]),
        "n_frames_other": float(oth_s["n_frames"]),
        "n_spot_fam_quad": n_spot_fam,
        "n_spot_nvl_quad": n_spot_nvl,
        "n_spot_other": n_spot_oth,
        "richness_fam_quad": float(fam_s["richness"]),
        "richness_nvl_quad": float(nvl_s["richness"]),
        "richness_other": float(oth_s["richness"]),
        "fam_richness_quad": float(fam_s["richness"]),
        "nvl_richness_quad": float(nvl_s["richness"]),
        "shannon_bits_fam_quad": float(fam_s["shannon_bits"]),
        "shannon_bits_nvl_quad": float(nvl_s["shannon_bits"]),
        "shannon_bits_other": float(oth_s["shannon_bits"]),
        "fam_shannon_quad": float(fam_s["shannon_bits"]),
        "nvl_shannon_quad": float(nvl_s["shannon_bits"]),
        "delta_shannon_quad": d_h,
        "dr_shannon_quad": dr_h,
        "delta_richness_quad": d_r,
        "dr_richness_quad": dr_r,
        "fam_hill2_quad": float(fam_s["hill2_eff"]),
        "nvl_hill2_quad": float(nvl_s["hill2_eff"]),
        "hill2_eff_other": float(oth_s["hill2_eff"]),
        "delta_hill2_quad": d_hill,
        "dr_hill2_quad": dr_hill,
        "dr_time_quad": dr_time,
        "time_contrast_eligible": bool(time_eligible),
        "contrast_eligible": bool(eligible),
        "object_cell_collision": False,
        "fam_cell_x": int(fam_cell[0]),
        "fam_cell_y": int(fam_cell[1]),
        "nvl_cell_x": int(nvl_cell[0]),
        "nvl_cell_y": int(nvl_cell[1]),
        "n_valid_spot": int(np.sum(ok)),
        "n_mapped_syll": int(np.sum(mapped)),
        "rotate_180": bool(rotate_180),
        "min_frames_n": int(min_frames),
    }


def assert_family_a_size(n_finite_p: int) -> None:
    if int(n_finite_p) != FAMILY_A_SIZE:
        raise AssertionError(
            f"Family QuadComp-A expects {FAMILY_A_SIZE} finite-p cells, got {n_finite_p}"
        )


def assert_time_family_a_size(n_finite_p: int) -> None:
    if int(n_finite_p) != TIME_FAMILY_A_SIZE:
        raise AssertionError(
            f"Family TimeQuad-A expects {TIME_FAMILY_A_SIZE} finite-p cells, got {n_finite_p}"
        )


def assert_level_family_a_size(n_finite_p: int) -> None:
    if int(n_finite_p) != LEVEL_FAMILY_A_SIZE:
        raise AssertionError(
            f"Family QuadLevel-A expects {LEVEL_FAMILY_A_SIZE} finite-p cells, got {n_finite_p}"
        )


def row_in_family_a(row: Mapping[str, object]) -> bool:
    return (
        str(row.get("session", "")) == LITMUS_A_SESSION
        and str(row.get("sex", "")) in FAMILY_SEXES
        and str(row.get("metric", "")) in FAMILY_METRICS
        and str(row.get("trial", TRIAL)) == TRIAL
        and str(row.get("test", "kruskal")) == "kruskal"
        and str(row.get("family", "QuadComp-A")) == "QuadComp-A"
    )
