"""NOR IMPRESS only: boss NOR# → wire session / trial.

Do not import this for VAST, RAM, or other NOR labs. Rules match
``archive/IMPRESS/my_nor_wip/utils/session_naming.py``. Docs:
``docs/vocab/NOR-IMPRESS-BOSS-SESSION-MAP.md``.
"""

from __future__ import annotations

from typing import Optional

# Cohorts that use NOR3 as 3 h recovery (wire NOR_REC3hr).
_NOR3_REC3HR_COHORTS = frozenset({"exp1", "exp3p1"})
# Cohort that uses NOR3 as 11 h recovery (wire NOR_REC11hr).
_NOR3_REC11HR_COHORTS = frozenset({"exp3p2"})
# Cohort that has NOR4 → NOR_REC11hr.
_NOR4_REC11HR_COHORTS = frozenset({"exp1"})

_TRIAL_FROM_SUFFIX = {
    "no_obj": "no_obj",
    "id_obj": "id_obj",
    "nvl_obj": "nvl_obj",
    # legacy export cells
    "identical_obj": "id_obj",
    "novel_obj": "nvl_obj",
}


def impress_nor_wire_session(boss_session: str, cohort: Optional[str]) -> str:
    """Map boss day token (``NOR1`` or ``NOR1_nvl_obj``) to wire ``session``.

    Raises ``ValueError`` if the boss prefix is unknown or cohort is required
    but missing / unsupported for that prefix.
    """
    token = str(boss_session).strip()
    if not token:
        raise ValueError("empty boss_session")

    # Accept NOR1, NOR1_nvl_obj, or bare prefix in mixed case.
    upper = token.upper()
    if upper.startswith("NOR1"):
        return "NOR_BL"
    if upper.startswith("NOR2"):
        return "NOR_TX"
    if upper.startswith("NOR3"):
        if cohort in _NOR3_REC3HR_COHORTS:
            return "NOR_REC3hr"
        if cohort in _NOR3_REC11HR_COHORTS:
            return "NOR_REC11hr"
        raise ValueError(
            f"NOR3 requires cohort in {_NOR3_REC3HR_COHORTS | _NOR3_REC11HR_COHORTS}; "
            f"got {cohort!r} for {boss_session!r}"
        )
    if upper.startswith("NOR4"):
        if cohort in _NOR4_REC11HR_COHORTS:
            return "NOR_REC11hr"
        raise ValueError(
            f"NOR4 requires cohort in {_NOR4_REC11HR_COHORTS}; "
            f"got {cohort!r} for {boss_session!r}"
        )
    raise ValueError(f"unrecognized NOR IMPRESS boss session: {boss_session!r}")


def impress_nor_wire_trial(
    *,
    boss_session: Optional[str] = None,
    filename: Optional[str] = None,
    default: Optional[str] = None,
) -> str:
    """Map boss suffix or filename cues to wire ``trial``.

    Preference: suffix on ``boss_session`` (``NOR1_nvl_obj``) → filename tokens
    (``NVL OBJ`` / ``ID OBJ`` / ``No OBJ``) → ``default`` if given.
    """
    if boss_session:
        parts = str(boss_session).strip().lower().split("_", 1)
        if len(parts) == 2 and parts[1] in _TRIAL_FROM_SUFFIX:
            return _TRIAL_FROM_SUFFIX[parts[1]]
        # already a trial token
        low = str(boss_session).strip().lower()
        if low in _TRIAL_FROM_SUFFIX:
            return _TRIAL_FROM_SUFFIX[low]

    if filename:
        name = str(filename).upper()
        if "NVL OBJ" in name or "NVL_OBJ" in name:
            return "nvl_obj"
        if "ID OBJ" in name or "ID_OBJ" in name:
            return "id_obj"
        if "NO OBJ" in name or "NO_OBJ" in name:
            return "no_obj"

    if default is not None:
        return _TRIAL_FROM_SUFFIX.get(default.lower(), default)

    raise ValueError(
        "could not infer wire trial from boss_session="
        f"{boss_session!r} filename={filename!r}"
    )


def impress_nor_condition_from_tx(tx: str) -> str:
    """Normalize IMPRESS ``ANIMAL_INFO['tx']`` to wire ``condition``."""
    raw = str(tx).strip()
    if raw.lower() == "nosd":
        return "noSD"
    if raw in {"noSD", "GHSD", "RBSD"}:
        return raw
    raise ValueError(f"unrecognized IMPRESS condition/tx: {tx!r}")
