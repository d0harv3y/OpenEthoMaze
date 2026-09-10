"""Join kpMS native group names to NOR session groups; cohort filters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterator

import h5py

_KPMS_PREFIX = "D:-nor vids-"
_SESSION_RE = re.compile(
    r"(NOR[1-4])\s+(NVL\s+OBJ|ID\s+OBJ|NO\s+OBJ)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class JoinedSession:
    kpms_key: str
    animal_id: str
    raw_session: str
    session: str
    trial: str
    condition: str
    sex: str
    cohort: str


def _h5_attr(node: Any, *names: str) -> str:
    """Read first present attr among *names* (live name first, then legacy)."""
    for name in names:
        if name in node.attrs:
            return str(node.attrs.get(name) or "")
    return ""


def parse_kpms_group(
    group_name: str,
    *,
    prefix: str = _KPMS_PREFIX,
    path_hyphens: int = 3,
) -> tuple[str, str]:
    """Return ``(animal_id, raw_session)`` from a native kpMS results group name."""
    if not group_name.startswith(prefix):
        raise ValueError(f"unexpected kpMS key prefix: {group_name[:80]!r}")
    rest = group_name[len(prefix) :]
    parts = rest.split("-", path_hyphens)
    if len(parts) != path_hyphens + 1:
        raise ValueError(f"cannot split kpMS key: {group_name[:120]!r}")
    animal_id = parts[2]
    filename = parts[3]
    m = _SESSION_RE.search(filename)
    if m is None:
        raise ValueError(f"no NOR session token in filename: {filename!r}")
    nor_n = m.group(1).upper()
    kind = re.sub(r"\s+", " ", m.group(2).upper())
    if kind == "NVL OBJ":
        raw = f"{nor_n}_nvl_obj"
    elif kind == "ID OBJ":
        raw = f"{nor_n}_id_obj"
    elif kind == "NO OBJ":
        raw = f"{nor_n}_no_obj"
    else:
        raise ValueError(f"unhandled trial token {kind!r} in {filename!r}")
    return animal_id, raw


def filter_cohort(nor_h5: h5py.File) -> dict[str, object]:
    """Keep animal groups with non-blank condition/sex; record drops.

    Returns a JSON-serializable summary with kept/dropped IDs and counts.
    On-disk NOR H5 may still use legacy attr ``tx`` until re-export.
    """
    kept: list[str] = []
    dropped_blank: list[dict[str, str]] = []
    dropped_non_animal: list[str] = []

    for key in sorted(nor_h5.keys()):
        node = nor_h5[key]
        if not isinstance(node, h5py.Group):
            dropped_non_animal.append(str(key))
            continue
        has_nor = any(str(s).startswith("NOR") for s in node.keys())
        if not has_nor:
            dropped_non_animal.append(str(key))
            continue
        condition = _h5_attr(node, "condition", "tx").strip()
        sex = str(node.attrs.get("sex", "") or "").strip()
        if not condition or not sex:
            dropped_blank.append(
                {
                    "animal_id": str(key),
                    "condition": condition,
                    "sex": sex,
                    "cohort": str(node.attrs.get("cohort", "") or ""),
                }
            )
            continue
        kept.append(str(key))

    return {
        "n_kept": len(kept),
        "kept_ids": kept,
        "n_dropped_blank_condition_or_sex": len(dropped_blank),
        "dropped_blank": dropped_blank,
        "n_dropped_non_animal": len(dropped_non_animal),
        "dropped_non_animal_ids": dropped_non_animal,
    }


def iter_joined_sessions(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    *,
    kept_ids: set[str],
    session: str | None = "NOR_TX",
) -> Iterator[JoinedSession]:
    """Yield joined sessions present in both HDF5s for kept animals."""
    for kpms_key in sorted(kpms_h5.keys()):
        try:
            animal_id, raw_session = parse_kpms_group(str(kpms_key))
        except ValueError:
            continue
        if animal_id not in kept_ids:
            continue
        if animal_id not in nor_h5 or raw_session not in nor_h5[animal_id]:
            continue
        sg = nor_h5[animal_id][raw_session]
        pl = _h5_attr(sg, "session", "phase_layer")
        if session is not None and pl != session:
            continue
        ag = nor_h5[animal_id]
        yield JoinedSession(
            kpms_key=str(kpms_key),
            animal_id=animal_id,
            raw_session=raw_session,
            session=pl,
            trial=_h5_attr(sg, "trial", "condition_layer"),
            condition=_h5_attr(ag, "condition", "tx"),
            sex=str(ag.attrs.get("sex", "") or ""),
            cohort=str(ag.attrs.get("cohort", "") or ""),
        )


def iter_nor_sessions(
    nor_h5: h5py.File,
    *,
    kept_ids: set[str],
    session: str | None = None,
) -> Iterator[JoinedSession]:
    """Yield NOR sessions for kept animals (no kpMS join)."""
    for animal_id in sorted(kept_ids):
        if animal_id not in nor_h5:
            continue
        ag = nor_h5[animal_id]
        if not isinstance(ag, h5py.Group):
            continue
        for raw_session in sorted(ag.keys()):
            sg = ag[raw_session]
            if not isinstance(sg, h5py.Group):
                continue
            pl = _h5_attr(sg, "session", "phase_layer")
            if session is not None and pl != session:
                continue
            if not (pl.startswith("NOR") or str(raw_session).startswith("NOR")):
                continue
            yield JoinedSession(
                kpms_key="",
                animal_id=str(animal_id),
                raw_session=str(raw_session),
                session=pl,
                trial=_h5_attr(sg, "trial", "condition_layer"),
                condition=_h5_attr(ag, "condition", "tx"),
                sex=str(ag.attrs.get("sex", "") or ""),
                cohort=str(ag.attrs.get("cohort", "") or ""),
            )
