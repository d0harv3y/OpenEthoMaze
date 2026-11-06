"""Per-animal nvl-side mass after fam-left alignment (Q5 SideMass Family A).

Grain: animal × session × nvl_obj. Spot xy from NOR H5; no kpMS.
Alignment parity with syllable_spatial_heatmap: rot180 when nvl on hist A
so fam sits left / nvl sits right. Midline = arena center cx.

Scores (not DR):
    frac_nvl_side      = #(x_aligned > cx) / n_valid
    mean_signed_x_m    = mean((x_aligned − cx) / ppm)   # + toward nvl
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

FAMILY_METRICS: tuple[str, ...] = ("frac_nvl_side", "mean_signed_x_m")
FAMILY_SESSIONS: tuple[str, ...] = (
    "NOR_BL",
    "NOR_TX",
    "NOR_REC3hr",
    "NOR_REC11hr",
)
FAMILY_SEXES: tuple[str, ...] = ("F", "M")
# Declared BH family size before any cohort peek (see Q5 SideMass Score Contract).
FAMILY_A_SIZE: int = len(FAMILY_METRICS) * len(FAMILY_SESSIONS) * len(FAMILY_SEXES)
TRIAL = "nvl_obj"
GRAIN = "animal × {session} × nvl_obj × spot_xy fam_left"


def rotate180_xy(
    x: np.ndarray,
    y: np.ndarray,
    *,
    cx: float,
    cy: float,
) -> tuple[np.ndarray, np.ndarray]:
    """180° about arena center (parity with syllable_spatial_heatmap)."""
    return (2.0 * cx - x), (2.0 * cy - y)


def side_mass_from_xy(
    x_px: np.ndarray,
    y_px: np.ndarray,
    valid: np.ndarray,
    *,
    cx: float,
    cy: float,
    ppm: float,
    rotate_180: bool,
) -> dict[str, float]:
    """Scalar side-mass from spot pixel tracks.

    Frames on the midline (x == cx after align) count in ``n_valid`` but neither
    side numerator — so ``frac_nvl_side + frac_fam_side`` may be < 1.
    """
    x = np.asarray(x_px, dtype=np.float64)
    y = np.asarray(y_px, dtype=np.float64)
    ok = np.asarray(valid, dtype=bool) & np.isfinite(x) & np.isfinite(y)
    if rotate_180:
        x, y = rotate180_xy(x, y, cx=cx, cy=cy)
    n_valid = int(np.sum(ok))
    if n_valid <= 0 or not np.isfinite(ppm) or ppm <= 0:
        return {
            "n_valid": float(n_valid),
            "frac_nvl_side": float("nan"),
            "frac_fam_side": float("nan"),
            "mean_signed_x_m": float("nan"),
            "rotate_180": float(1.0 if rotate_180 else 0.0),
        }
    xa = x[ok]
    n_nvl = int(np.sum(xa > cx))
    n_fam = int(np.sum(xa < cx))
    signed_m = (xa - cx) / float(ppm)
    return {
        "n_valid": float(n_valid),
        "frac_nvl_side": float(n_nvl / n_valid),
        "frac_fam_side": float(n_fam / n_valid),
        "mean_signed_x_m": float(np.mean(signed_m)),
        "rotate_180": float(1.0 if rotate_180 else 0.0),
    }


def family_a_cell_keys() -> list[tuple[str, str, str]]:
    """All (session, sex, metric) keys in BH Family SideMass-A."""
    return [
        (session, sex, metric)
        for session in FAMILY_SESSIONS
        for sex in FAMILY_SEXES
        for metric in FAMILY_METRICS
    ]


def assert_family_a_size(n_finite_p: int) -> None:
    """Fail fast if the test table does not match the declared family."""
    if int(n_finite_p) != FAMILY_A_SIZE:
        raise AssertionError(
            f"Family SideMass-A expects {FAMILY_A_SIZE} finite-p cells, got {n_finite_p}"
        )


def row_in_family_a(row: Mapping[str, object]) -> bool:
    return (
        str(row.get("session", "")) in FAMILY_SESSIONS
        and str(row.get("sex", "")) in FAMILY_SEXES
        and str(row.get("metric", "")) in FAMILY_METRICS
        and str(row.get("trial", TRIAL)) == TRIAL
        and str(row.get("test", "kruskal")) == "kruskal"
    )
