from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import h5py

if TYPE_CHECKING:
    from ..io.file_discovery import TrialManifest


def ram_sessions_equivalent(a: str, b: str) -> bool:
    """True if *a* and *b* differ only by underscore vs hyphen (e.g. ``train_1`` vs ``train-1``)."""
    return str(a).strip().replace("_", "-") == str(b).strip().replace("_", "-")


def canonical_ram_trial(t: str) -> str:
    """Map ``1``, ``T1``, ``t01`` to zero-padded ``T01`` for matching manifest vs CLI."""
    s = str(t).strip()
    if not s:
        return s
    if s.isdigit():
        return f"T{int(s):02d}"
    if len(s) >= 2 and s[0].upper() == "T" and s[1:].isdigit():
        return f"T{int(s[1:]):02d}"
    return s


def ram_trials_equivalent(a: str, b: str) -> bool:
    """True if trial labels refer to the same index (``1`` vs ``T01``)."""
    return canonical_ram_trial(a) == canonical_ram_trial(b)


def _session_candidates(session: str) -> list[str]:
    s = str(session).strip()
    order: list[str] = []
    seen: set[str] = set()
    for c in (s, s.replace("_", "-"), s.replace("-", "_")):
        if c and c not in seen:
            seen.add(c)
            order.append(c)
    return order


def _trial_candidates(trial: str) -> list[str]:
    t = str(trial).strip()
    order: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        if x and x not in seen:
            seen.add(x)
            order.append(x)

    add(t)
    add(canonical_ram_trial(t))
    if t.isdigit():
        add(f"T{int(t):02d}")
    elif len(t) >= 2 and t[0].upper() == "T" and t[1:].isdigit():
        n = int(t[1:])
        add(str(n))
    return order


def _h5_trial_group_exists(h5: h5py.File, key: TrialKey) -> bool:
    p = key.path().lstrip("/")
    try:
        h5[p]
        return True
    except KeyError:
        return False


def resolve_trial_key_for_hdf5(h5: h5py.File, key: TrialKey) -> TrialKey:
    """
    Return a :class:`TrialKey` whose HDF5 path exists.

    Tolerates legacy RAM databases that use ``train_1`` while manifests / imports use
    ``train-1``, and numeric trial labels vs ``T01``.
    """
    if _h5_trial_group_exists(h5, key):
        return key
    aid = str(key.animal_id)
    if aid not in h5:
        return key
    g_aid = h5[aid]
    for sess in _session_candidates(key.session):
        if sess not in g_aid:
            continue
        g_sess = g_aid[sess]
        for tri in _trial_candidates(key.trial):
            if tri not in g_sess:
                continue
            if sess == key.session and tri == key.trial:
                return key
            return TrialKey(animal_id=key.animal_id, session=sess, trial=tri)
    return key


@dataclass(frozen=True)
class TrialKey:
    """Unique identifier for a trial in the database."""

    animal_id: str
    session: str
    trial: str

    def path(self) -> str:
        return f"/{self.animal_id}/{self.session}/{self.trial}"

    @property
    def phase(self) -> str:
        return "habituation" if self.session.upper().startswith("H") else "experimental"

    @classmethod
    def from_manifest(cls, manifest: "TrialManifest") -> "TrialKey":
        return cls(
            animal_id=manifest.animal_id,
            session=manifest.session,
            trial=manifest.trial,
        )
