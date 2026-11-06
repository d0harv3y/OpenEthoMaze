"""Display tokens for object-prox figures (matplotlib + Plotly)."""

from __future__ import annotations

OCC_METRICS = ("frac_near_fam", "frac_near_nvl")
OCC_LAB = {"frac_near_fam": "fam prox", "frac_near_nvl": "nvl prox"}
OCC_STEM = {
    "frac_near_fam": "fig_object_prox_occupancy_fam",
    "frac_near_nvl": "fig_object_prox_occupancy_nvl",
}


def p_compact(p: float) -> str:
    if p != p:  # NaN
        return "n/a"
    if p < 1e-4:
        return "<10⁻⁴"
    if p < 0.001:
        return f"{p:.1e}"
    return f"{p:.2f}"
