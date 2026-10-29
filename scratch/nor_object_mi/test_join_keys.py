"""Litmus for kpMS ↔ NOR join key parsing (legacy path + recog bare stems)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.join_keys import parse_kpms_group, _wire_trial  # noqa: E402


def test_parse_legacy_path_key() -> None:
    key = (
        "D:-nor vids-standard format-exp1-3115-"
        "NOR1 NVL OBJ Arena 5 07-03-25 3115 06-14.h5"
    )
    animal, raw = parse_kpms_group(key)
    assert animal == "3115"
    assert raw == "NOR1_nvl_obj"


def test_parse_recog_bare_stem() -> None:
    key = "NOR1 NVL OBJ Arena 1 04-09-25 55 3013 17-17"
    animal, raw = parse_kpms_group(key)
    assert animal == "3013"
    assert raw == "NOR1_nvl_obj"


def test_wire_trial_legacy_cells() -> None:
    assert _wire_trial("novel_obj") == "nvl_obj"
    assert _wire_trial("identical_obj") == "id_obj"
    assert _wire_trial("nvl_obj") == "nvl_obj"
