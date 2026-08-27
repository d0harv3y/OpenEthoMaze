"""Estimate the two historical object-placement loci for no_obj pseudo-targets."""

from __future__ import annotations

from typing import Optional, Sequence

import h5py
import numpy as np


def _session_object_centers_px(session: h5py.Group) -> list[np.ndarray]:
    if "objects" not in session:
        return []
    out: list[np.ndarray] = []
    for key in session["objects"].keys():
        if not str(key).startswith("object_"):
            continue
        g = session["objects"][key]
        if "center" not in g:
            continue
        out.append(np.asarray(g["center"][()], dtype=np.float64).ravel()[:2])
    return out


def collect_phase_object_centers_px(
    nor_h5: h5py.File,
    animal_id: str,
    phase_layer: str,
    *,
    condition_layers: tuple[str, ...] = ("identical_obj", "novel_obj"),
) -> np.ndarray:
    """Stack object centers (px) from object-present sessions in one phase."""
    if animal_id not in nor_h5:
        return np.zeros((0, 2), dtype=np.float64)
    pts: list[np.ndarray] = []
    wanted = set(condition_layers)
    for raw in nor_h5[animal_id].keys():
        sg = nor_h5[animal_id][raw]
        if str(sg.attrs.get("phase_layer", "") or "") != phase_layer:
            continue
        if str(sg.attrs.get("condition_layer", "") or "") not in wanted:
            continue
        pts.extend(_session_object_centers_px(sg))
    if not pts:
        return np.zeros((0, 2), dtype=np.float64)
    return np.vstack(pts)


def two_means_loci_px(points: np.ndarray, *, n_iter: int = 25) -> np.ndarray:
    """Return shape (2, 2) locus means via simple 2-means (no sklearn)."""
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    if pts.shape[0] < 2:
        raise ValueError(f"need >=2 object centers for loci, got {pts.shape[0]}")
    # Init: farthest pair
    d2 = ((pts[:, None, :] - pts[None, :, :]) ** 2).sum(axis=2)
    i, j = np.unravel_index(int(np.argmax(d2)), d2.shape)
    centers = np.stack([pts[i], pts[j]], axis=0)
    for _ in range(n_iter):
        dist = ((pts[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = np.argmin(dist, axis=1)
        new = centers.copy()
        for k in (0, 1):
            mask = labels == k
            if np.any(mask):
                new[k] = pts[mask].mean(axis=0)
        if np.allclose(new, centers):
            centers = new
            break
        centers = new
    # Stable order: lower x first
    order = np.argsort(centers[:, 0])
    return centers[order]


def loci_for_animal_phase(
    nor_h5: h5py.File,
    animal_id: str,
    phase_layer: str,
) -> Optional[np.ndarray]:
    """Two placement loci (px) averaged from that animal's object-present trials."""
    pts = collect_phase_object_centers_px(nor_h5, animal_id, phase_layer)
    if pts.shape[0] < 2:
        return None
    return two_means_loci_px(pts)


def match_centers_to_loci(
    centers_px: Sequence[np.ndarray],
    loci_px: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Assign two object centers to spatial loci A/B (lower-x = A).

    Returns ``(center_for_locus_a, center_for_locus_b)`` in px.
    Uses the permutation that minimizes sum of squared distances.
    """
    loci = np.asarray(loci_px, dtype=np.float64).reshape(2, 2)
    pts = [np.asarray(c, dtype=np.float64).ravel()[:2] for c in centers_px]
    if len(pts) < 2:
        raise ValueError(f"need two centers to match to loci, got {len(pts)}")
    # Prefer exact two; if more, take the two farthest (rare)
    if len(pts) > 2:
        arr = np.stack(pts, axis=0)
        d2 = ((arr[:, None, :] - arr[None, :, :]) ** 2).sum(axis=2)
        i, j = np.unravel_index(int(np.argmax(d2)), d2.shape)
        pts = [arr[i], arr[j]]
    p0, p1 = pts[0], pts[1]
    cost_direct = float(np.sum((p0 - loci[0]) ** 2) + np.sum((p1 - loci[1]) ** 2))
    cost_swap = float(np.sum((p1 - loci[0]) ** 2) + np.sum((p0 - loci[1]) ** 2))
    if cost_direct <= cost_swap:
        return p0, p1
    return p1, p0
