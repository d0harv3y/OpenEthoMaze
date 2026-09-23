"""Discover NOR SLEAP sidecars under ``standard format/exp*/{animal_id}/``."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# NOR1 NVL OBJ Arena 1 04-09-25 55 3013 17-17
# NOR1 NO OBJ Arena 5 04-03-25 3007 14-16  (optional sequence number)
_NOR_SLP_STEM = re.compile(
    r"^NOR(\d+)\s+"
    r"(NO|ID|NVL)\s+OBJ\s+"
    r"Arena\s+(\d+)\s+"
    r"(\d{2}-\d{2}-\d{2})\s+"
    r"(?:(\d+)\s+)?"
    r"(\d{4})\s+"
    r"(\d{1,2}-\d{2})$",
    re.IGNORECASE,
)

_OBJ_TO_TRIAL = {
    "NO": "no_obj",
    "ID": "id_obj",
    "NVL": "nvl_obj",
}


@dataclass(frozen=True)
class NorSlpRecording:
    """One parsed NOR SLEAP sidecar under an animal folder."""

    path: Path
    cohort: str
    animal_id: str
    session: str  # NOR1..NOR4
    trial_wire: str  # no_obj | id_obj | nvl_obj
    arena: str
    date: str
    stem: str


@dataclass(frozen=True)
class NorAnimalBundle:
    """All usable SLEAP recordings for one animal leaf."""

    cohort: str
    animal_id: str
    animal_dir: Path
    recordings: tuple[NorSlpRecording, ...]


def stem_from_slp_name(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".h5.slp"):
        return name[: -len(".h5.slp")]
    if lower.endswith(".slp"):
        return name[: -len(".slp")]
    return Path(name).stem


def parse_nor_slp_stem(stem: str) -> tuple[str, str, str, str, str] | None:
    """
    Return ``(nor_i, obj, arena, date, animal_id)`` or None if not a NOR object trial.
    """
    m = _NOR_SLP_STEM.match(stem.strip())
    if m is None:
        return None
    nor_i, obj, arena, date, _seq, animal_id, _clock = m.groups()
    return nor_i, obj.upper(), arena, date, animal_id


def discover_nor_animal_bundles(data_root: Path) -> list[NorAnimalBundle]:
    """
    Walk ``data_root/exp*/{animal_id}/**/*.slp`` (excludes Habituation by name).
    """
    root = Path(data_root)
    if not root.is_dir():
        raise FileNotFoundError(f"data_root not found: {root}")

    bundles: list[NorAnimalBundle] = []
    for cohort_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name.lower().startswith("exp")):
        cohort = cohort_dir.name
        for animal_dir in sorted(p for p in cohort_dir.iterdir() if p.is_dir()):
            animal_id = animal_dir.name.strip()
            if not animal_id.isdigit():
                continue
            recs: list[NorSlpRecording] = []
            for slp in sorted(animal_dir.rglob("*.slp")):
                if "habituation" in slp.name.lower():
                    continue
                stem = stem_from_slp_name(slp.name)
                parsed = parse_nor_slp_stem(stem)
                if parsed is None:
                    continue
                nor_i, obj, arena, date, stem_animal = parsed
                if stem_animal != animal_id:
                    # Prefer folder ID; skip mismatches loudly via omit
                    continue
                trial_wire = _OBJ_TO_TRIAL[obj]
                recs.append(
                    NorSlpRecording(
                        path=slp.resolve(),
                        cohort=cohort,
                        animal_id=animal_id,
                        session=f"NOR{nor_i}",
                        trial_wire=trial_wire,
                        arena=arena,
                        date=date,
                        stem=stem,
                    )
                )
            if recs:
                bundles.append(
                    NorAnimalBundle(
                        cohort=cohort,
                        animal_id=animal_id,
                        animal_dir=animal_dir.resolve(),
                        recordings=tuple(recs),
                    )
                )
    return bundles


def write_animal_manifest_csv(bundle: NorAnimalBundle, out_path: Path) -> Path:
    """Write a SLEAP-only trial_manifest.csv for one animal (blank input_h5_path)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    per_key: dict[tuple[str, str], int] = defaultdict(int)
    rows: list[dict[str, str]] = []
    for rec in bundle.recordings:
        key = (rec.session, rec.trial_wire)
        per_key[key] += 1
        trial = f"T{per_key[key]:02d}"
        rows.append(
            {
                "animal_id": rec.animal_id,
                "session": rec.session,
                "trial": trial,
                "phase": "experimental",
                "input_h5_path": "",
                "video_path": "",
                "sleap_path": str(rec.path),
                "kpms_recording_key": rec.stem,
                "has_tracking_pose": "0",
                "cohort": rec.cohort,
                "sex": "",
                "condition": "",
                # Keep object trial wire for humans; fit ignores unknown columns.
                "object_trial": rec.trial_wire,
                "arena": rec.arena,
                "date": rec.date,
            }
        )
    fields = list(rows[0].keys()) if rows else [
        "animal_id",
        "session",
        "trial",
        "phase",
        "input_h5_path",
        "video_path",
        "sleap_path",
        "kpms_recording_key",
        "has_tracking_pose",
        "cohort",
        "sex",
        "condition",
        "object_trial",
        "arena",
        "date",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return out_path
