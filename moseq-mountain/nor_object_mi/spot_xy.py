"""Reconstruct NOR ``spot`` synthetic keypoint and object distances."""

from __future__ import annotations

from typing import Mapping, Sequence

import h5py
import numpy as np

SPOT_NODES: tuple[str, ...] = ("nose", "neck", "spine")


def _node_xy(sleap: h5py.Group, node: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    g = sleap[node]
    x = np.asarray(g["x"][()], dtype=np.float64)
    y = np.asarray(g["y"][()], dtype=np.float64)
    if "visible" in g:
        vis = np.asarray(g["visible"][()], dtype=bool)
    else:
        vis = np.isfinite(x) & np.isfinite(y)
    return x, y, vis


def spot_xy_px(sleap: h5py.Group) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Mean of nose/neck/spine (px). Invalid frames → NaN xy, False valid."""
    missing = [n for n in SPOT_NODES if n not in sleap]
    if missing:
        raise KeyError(f"spot requires nodes {SPOT_NODES}, missing {missing}")

    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    viss: list[np.ndarray] = []
    for node in SPOT_NODES:
        x, y, vis = _node_xy(sleap, node)
        xs.append(x)
        ys.append(y)
        viss.append(vis)

    n = int(xs[0].shape[0])
    stack_x = np.stack(xs, axis=0)
    stack_y = np.stack(ys, axis=0)
    stack_v = np.stack(viss, axis=0)
    # Require at least one visible node; average only visible contributors.
    valid = np.any(stack_v, axis=0)
    w = stack_v.astype(np.float64)
    w_sum = w.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        x_out = np.where(valid, (stack_x * w).sum(axis=0) / w_sum, np.nan)
        y_out = np.where(valid, (stack_y * w).sum(axis=0) / w_sum, np.nan)
    if x_out.shape[0] != n:
        raise RuntimeError("spot length mismatch")
    return x_out, y_out, valid


def pixels_per_meter(session: h5py.Group) -> float:
    objs = session["objects"]
    if "arena" in objs and "pixels_per_meter" in objs["arena"]:
        return float(np.asarray(objs["arena"]["pixels_per_meter"][()]).item())
    ppm = objs.attrs.get("pixels_per_meter")
    if ppm is None:
        raise KeyError("pixels_per_meter missing on objects/arena")
    return float(ppm)


def object_centers_px(session: h5py.Group) -> dict[str, np.ndarray]:
    """Map ``object_0`` → center xy (px)."""
    out: dict[str, np.ndarray] = {}
    if "objects" not in session:
        return out
    for key in session["objects"].keys():
        if not str(key).startswith("object_"):
            continue
        g = session["objects"][key]
        if "center" not in g:
            continue
        out[str(key)] = np.asarray(g["center"][()], dtype=np.float64).ravel()[:2]
    return out


def spot_xy_m(session: h5py.Group) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Return spot x_m, y_m, valid, ppm."""
    if "sleap_data" not in session:
        raise KeyError("sleap_data missing")
    x_px, y_px, valid = spot_xy_px(session["sleap_data"])
    ppm = pixels_per_meter(session)
    return x_px / ppm, y_px / ppm, valid, ppm


def dist_to_center_m(
    x_m: np.ndarray,
    y_m: np.ndarray,
    valid: np.ndarray,
    center_px: np.ndarray,
    ppm: float,
) -> np.ndarray:
    cx, cy = float(center_px[0]) / ppm, float(center_px[1]) / ppm
    out = np.full(x_m.shape, np.nan, dtype=np.float64)
    mask = valid & np.isfinite(x_m) & np.isfinite(y_m)
    out[mask] = np.hypot(x_m[mask] - cx, y_m[mask] - cy)
    return out


def nearest_distance_m(
    session: h5py.Group,
    centers_px: Sequence[np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """Per-frame min spot distance (m) to any of the given centers (px)."""
    if not centers_px:
        raise ValueError("centers_px empty")
    x_m, y_m, valid, ppm = spot_xy_m(session)
    stacked = [dist_to_center_m(x_m, y_m, valid, np.asarray(c, dtype=np.float64).ravel()[:2], ppm) for c in centers_px]
    arr = np.stack(stacked, axis=0)
    nearest = np.full(x_m.shape, np.nan, dtype=np.float64)
    if np.any(valid):
        with np.errstate(invalid="ignore"):
            nearest[valid] = np.nanmin(arr[:, valid], axis=0)
    return nearest, valid


def all_object_distances_m(session: h5py.Group) -> tuple[list[str], list[np.ndarray], np.ndarray]:
    """Per-frame spot distances (m) to every ``object_*`` center (sorted keys)."""
    x_m, y_m, valid, ppm = spot_xy_m(session)
    centers = object_centers_px(session)
    keys = sorted(centers)
    dists = [dist_to_center_m(x_m, y_m, valid, centers[k], ppm) for k in keys]
    return keys, dists, valid


def role_distances_m(
    session: h5py.Group,
    fam_nvl: Mapping[str, str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-frame distances (m) to fam and nvl object centers via spot.

    ``fam_nvl`` maps raw object_id (e.g. ``object_0``) → ``fam`` | ``nvl``.
    """
    x_m, y_m, valid, ppm = spot_xy_m(session)
    centers = object_centers_px(session)
    fam_key = next((k for k, v in fam_nvl.items() if v == "fam"), None)
    nvl_key = next((k for k, v in fam_nvl.items() if v == "nvl"), None)
    if fam_key is None or nvl_key is None:
        raise ValueError(f"fam/nvl map incomplete: {dict(fam_nvl)}")
    if fam_key not in centers or nvl_key not in centers:
        raise KeyError(f"centers missing for {fam_key!r} / {nvl_key!r}")
    d_fam = dist_to_center_m(x_m, y_m, valid, centers[fam_key], ppm)
    d_nvl = dist_to_center_m(x_m, y_m, valid, centers[nvl_key], ppm)
    return d_fam, d_nvl, valid
