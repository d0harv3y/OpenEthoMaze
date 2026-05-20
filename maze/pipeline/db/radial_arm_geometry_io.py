"""HDF5 dataset tree for ``task_data/radial_arm`` geometry (RAM trials).

Layout under ``task_data/radial_arm``:

- ``calibration/`` — scalar float datasets (``template_center_x_px``, …) plus
  attr ``edit_region_name`` when present.
- ``template_params/`` — scalar float datasets for template dimensions.
- ``template_regions_cm/`` — one float64 dataset per region name, shape ``(N, 2)``.

Legacy JSON attributes (``geometry_payload``, ``template_params``, …) are removed
on write. :func:`read_radial_arm_geometry_tree` reads the tree first and falls
back to legacy attrs only when the tree is absent.
"""

from __future__ import annotations

import json
import re
from typing import Any

import h5py
import numpy as np

_SAFE_REGION = re.compile(r"[^a-zA-Z0-9_\-]+")


def _decode_attr(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def _purge_legacy_ram_geometry_attrs(g_task: h5py.Group) -> None:
    for key in ("geometry_payload", "template_params", "calibration", "template_regions_cm"):
        if key in g_task.attrs:
            del g_task.attrs[key]


def _remove_child_if_present(g_task: h5py.Group, name: str) -> None:
    if name in g_task:
        del g_task[name]


def write_radial_arm_geometry_tree(g_task: h5py.Group, geometry_payload: dict[str, Any]) -> None:
    """Write geometry from the same dict shape as :func:`compute_radial_arm_settings_payloads`."""
    _purge_legacy_ram_geometry_attrs(g_task)
    for child in ("calibration", "template_params", "template_regions_cm"):
        _remove_child_if_present(g_task, child)

    cal = geometry_payload.get("calibration") or {}
    g_cal = g_task.create_group("calibration")
    for key, val in cal.items():
        if key == "edit_region_name":
            g_cal.attrs["edit_region_name"] = str(val or "")
            continue
        try:
            g_cal.create_dataset(key, data=np.float64(float(val)))
        except (TypeError, ValueError):
            continue

    tp = geometry_payload.get("template_params") or {}
    g_tp = g_task.create_group("template_params")
    for key, val in tp.items():
        try:
            g_tp.create_dataset(key, data=np.float64(float(val)))
        except (TypeError, ValueError):
            continue

    regions = geometry_payload.get("template_regions_cm") or {}
    g_reg = g_task.create_group("template_regions_cm")
    for raw_name, poly in regions.items():
        name = _SAFE_REGION.sub("_", str(raw_name)).strip("_") or "region"
        arr = np.asarray(poly, dtype=np.float64)
        if arr.size == 0:
            continue
        if arr.ndim == 1:
            arr = arr.reshape(-1, 2) if arr.size % 2 == 0 else arr.reshape(1, -1)
        if arr.shape[-1] != 2:
            continue
        g_reg.create_dataset(name, data=arr, compression="gzip")


def _scalar_ds_to_float(g: h5py.Group, key: str) -> float | None:
    if key not in g:
        return None
    return float(np.asarray(g[key])[()])


def _read_scalar_group(g: h5py.Group) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in g.keys():
        try:
            out[str(key)] = float(np.asarray(g[key])[()])
        except (TypeError, ValueError, KeyError):
            continue
    for ak, av in g.attrs.items():
        out[str(ak)] = _decode_attr(av)
    return out


def _legacy_geometry_payload_from_attrs(g_task: h5py.Group) -> dict[str, Any]:
    raw = g_task.attrs.get("geometry_payload", "{}")
    raw = _decode_attr(raw)
    try:
        loaded = json.loads(str(raw) or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        loaded = {}
    if isinstance(loaded, dict) and loaded:
        return loaded

    # Piecemeal JSON attrs
    def _load(name: str) -> dict[str, Any]:
        r = g_task.attrs.get(name, "{}")
        r = _decode_attr(r)
        try:
            d = json.loads(str(r) or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return d if isinstance(d, dict) else {}

    tp = _load("template_params")
    cal = _load("calibration")
    tr = _load("template_regions_cm")
    if not tp and not cal and not tr:
        return {}
    return {
        "template_params": tp,
        "calibration": cal,
        "template_regions_cm": tr,
    }


def read_radial_arm_geometry_tree(g_task: h5py.Group) -> dict[str, Any]:
    """Return ``geometry_payload``-shaped dict (template_params, calibration, template_regions_cm)."""
    if "calibration" not in g_task or "template_params" not in g_task:
        return _legacy_geometry_payload_from_attrs(g_task)

    calibration = _read_scalar_group(g_task["calibration"])
    template_params = _read_scalar_group(g_task["template_params"])

    regions: dict[str, Any] = {}
    if "template_regions_cm" in g_task:
        g_reg = g_task["template_regions_cm"]
        for name in g_reg.keys():
            regions[str(name)] = np.asarray(g_reg[name][:], dtype=float).tolist()

    return {
        "template_params": template_params,
        "calibration": calibration,
        "template_regions_cm": regions,
    }
