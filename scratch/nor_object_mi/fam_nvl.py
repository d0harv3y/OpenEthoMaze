"""Familiar / novel object role assignment (parity with NOR FamNvlAssigner)."""

from __future__ import annotations

from typing import Optional

import h5py


def _base_type(name: str) -> str:
    name = (name or "").strip()
    return name[:-1] if name.endswith("*") else name


def _shape_token(name: str) -> str:
    parts = (name or "").split()
    return parts[-1] if parts else ""


def _color_token(name: str) -> str:
    n = (name or "").strip().lower()
    if n.startswith("black "):
        return "black"
    if n.startswith("white "):
        return "white"
    if n.startswith("stripe "):
        return "stripe"
    return ""


def _score_nvl_candidates(
    candidates: list[tuple[str, str]],
    fam_types: list[str],
) -> tuple[str, str]:
    fam_bases = {_base_type(t).strip().lower() for t in fam_types if t}
    fam_shapes = {_shape_token(_base_type(t)).strip().lower() for t in fam_types if t}
    fam_colors = {_color_token(t) for t in fam_types if t}
    scores: dict[str, float] = {}
    for raw_id, typ in candidates:
        base = _base_type(typ).strip().lower()
        shape = _shape_token(base).strip().lower()
        color = _color_token(base)
        s = 0.0
        if base in fam_bases:
            s += 5.0
        if typ.endswith("*") and base in fam_bases:
            s += 1.0
        if shape and shape in fam_shapes:
            s += 0.5
        if fam_colors and color in fam_colors:
            s += 0.25
        scores[raw_id] = s
    ordered = sorted(
        [c for c in candidates if c[1] != "arena"],
        key=lambda x: scores.get(x[0], 0.0),
        reverse=True,
    )
    fam_choice = ordered[0][0] if ordered else ""
    nvl_choice = ordered[1][0] if len(ordered) > 1 else ""
    return fam_choice, nvl_choice


def _familiar_types_from_id_obj(nor_h5: h5py.File, animal_id: str, nvl_session: str) -> list[str]:
    nor_part = nvl_session.split("_")[0] if "_" in nvl_session else nvl_session
    id_sess = f"{nor_part}_id_obj"
    if animal_id not in nor_h5 or id_sess not in nor_h5[animal_id]:
        return []
    sg = nor_h5[animal_id][id_sess]
    fam_types: list[str] = []
    if "exploration_metrics" in sg and "object_details" in sg["exploration_metrics"]:
        od = sg["exploration_metrics"]["object_details"]
        for k in od.keys():
            if not str(k).startswith("object_"):
                continue
            typ = str(od[k].attrs.get("object_type", "") or "")
            if typ and typ != "arena" and typ not in fam_types:
                fam_types.append(typ)
    if not fam_types and "objects" in sg:
        for k in sg["objects"].keys():
            if not str(k).startswith("object_"):
                continue
            obj = sg["objects"][k]
            typ = str(obj.attrs.get("class_name", "") or obj.attrs.get("object_type", "") or "")
            if typ and typ != "arena" and typ not in fam_types:
                fam_types.append(typ)
    return fam_types


def fam_nvl_map_for_session(
    nor_h5: h5py.File,
    animal_id: str,
    raw_session: str,
) -> Optional[dict[str, str]]:
    """Return ``{object_id: 'fam'|'nvl'}`` for ``*_nvl_obj`` sessions, else None."""
    if "nvl_obj" not in raw_session:
        return None
    if animal_id not in nor_h5 or raw_session not in nor_h5[animal_id]:
        return None
    sg = nor_h5[animal_id][raw_session]
    if "exploration_metrics" not in sg or "object_details" not in sg["exploration_metrics"]:
        return None
    od = sg["exploration_metrics"]["object_details"]
    candidates: list[tuple[str, str]] = []
    for obj_key in od.keys():
        if not str(obj_key).startswith("object_"):
            continue
        og = od[obj_key]
        raw_obj_id = str(og.attrs.get("object_id", "") or obj_key)
        obj_type = str(og.attrs.get("object_type", "") or "")
        if not raw_obj_id or not obj_type:
            continue
        candidates.append((raw_obj_id, obj_type))
    if len(candidates) < 2:
        return None
    fam_types = _familiar_types_from_id_obj(nor_h5, animal_id, raw_session)
    fam_choice, nvl_choice = _score_nvl_candidates(candidates, fam_types)
    if not fam_choice or not nvl_choice:
        return None
    return {fam_choice: "fam", nvl_choice: "nvl"}
