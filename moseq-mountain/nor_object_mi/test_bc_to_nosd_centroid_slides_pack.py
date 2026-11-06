"""Litmus checks for BC-to-noSD-centroid atypicality pack."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.bc_to_nosd_centroid_slides_pack import (
    animal_counts_table,
    bc_to_nosd_centroid_cell,
    build_pack,
)
from nor_object_mi.simpler_first_condition_extras import _counts_to_matrix


def _toy_bouts() -> pd.DataFrame:
    """noSD near [1,0]; GHSD/RBSD near [0,1] → SD arms far from noSD centroid."""
    rows = []
    for aid, sex, tx, p0 in (
        ("a", "F", "noSD", 0.95),
        ("b", "F", "noSD", 0.90),
        ("c", "F", "noSD", 0.92),
        ("d", "F", "GHSD", 0.10),
        ("e", "F", "GHSD", 0.08),
        ("f", "F", "RBSD", 0.12),
        ("g", "F", "RBSD", 0.05),
    ):
        rows.append(
            {
                "animal_id": aid,
                "sex": sex,
                "condition": tx,
                "session": "NOR_TX",
                "trial": "nvl_obj",
                "raw_syllable_id": 0,
                "bout_frames": p0 * 100,
            }
        )
        rows.append(
            {
                "animal_id": aid,
                "sex": sex,
                "condition": tx,
                "session": "NOR_TX",
                "trial": "nvl_obj",
                "raw_syllable_id": 1,
                "bout_frames": (1.0 - p0) * 100,
            }
        )
    return pd.DataFrame(rows)


def test_sd_farther_than_nosd_loo() -> None:
    ac = animal_counts_table(_toy_bouts())
    scored = bc_to_nosd_centroid_cell(
        ac, session="NOR_TX", trial="nvl_obj", sex="F", model="m"
    )
    nosd = scored[scored["condition"] == "noSD"]["p"].to_numpy(dtype=float)
    other = scored[scored["condition"] != "noSD"]["p"].to_numpy(dtype=float)
    assert np.all(np.isfinite(nosd)) and np.all(np.isfinite(other))
    assert float(np.median(other)) > float(np.median(nosd))
    # LOO: noSD atypicality should be small but > 0 (they aren't identical)
    assert float(np.median(nosd)) < 0.2


def test_loo_excludes_self() -> None:
    """Single noSD with unique composition: LOO needs ≥1 other noSD."""
    rows = []
    for aid, tx, p0 in (("a", "noSD", 1.0), ("b", "noSD", 0.5), ("c", "GHSD", 0.0)):
        rows.append(
            {
                "animal_id": aid,
                "sex": "F",
                "condition": tx,
                "session": "NOR_BL",
                "trial": "no_obj",
                "raw_syllable_id": 0,
                "bout_frames": p0 * 100 + 1e-9,
            }
        )
        rows.append(
            {
                "animal_id": aid,
                "sex": "F",
                "condition": tx,
                "session": "NOR_BL",
                "trial": "no_obj",
                "raw_syllable_id": 1,
                "bout_frames": (1.0 - p0) * 100 + 1e-9,
            }
        )
    ac = animal_counts_table(pd.DataFrame(rows))
    scored = bc_to_nosd_centroid_cell(
        ac, session="NOR_BL", trial="no_obj", sex="F", model="m"
    )
    a = float(scored.loc[scored["animal_id"] == "a", "p"].iloc[0])
    # a is extreme noSD; LOO centroid is b → BC large
    assert a > 0.3
    assert int(scored.loc[scored["animal_id"] == "a", "n_nosd_ref"].iloc[0]) == 1


def test_build_pack_kruskal_family() -> None:
    # Expand toy across sessions/trials/sexes lightly via copies
    base = _toy_bouts()
    parts = []
    for session in ("NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr"):
        for trial in ("no_obj", "id_obj", "nvl_obj"):
            for sex in ("F", "M"):
                g = base.copy()
                g["session"] = session
                g["trial"] = trial
                g["sex"] = sex
                g["animal_id"] = g["animal_id"] + f"_{sex}"
                parts.append(g)
    ac = animal_counts_table(pd.concat(parts, ignore_index=True))
    scored_parts = []
    for session in ("NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr"):
        for trial in ("no_obj", "id_obj", "nvl_obj"):
            for sex in ("F", "M"):
                scored_parts.append(
                    bc_to_nosd_centroid_cell(
                        ac, session=session, trial=trial, sex=sex, model="m1"
                    )
                )
                scored_parts.append(
                    bc_to_nosd_centroid_cell(
                        ac, session=session, trial=trial, sex=sex, model="m2"
                    )
                )
    levels = pd.concat(scored_parts, ignore_index=True)
    pack = build_pack(levels)
    assert len(pack["kruskal_level"]) == 24
    assert pack["kruskal_per_model_level"]["model"].nunique() == 2
