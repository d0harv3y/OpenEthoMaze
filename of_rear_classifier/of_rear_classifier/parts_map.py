"""Sturman OFT part names ↔ SA-TVM (SuperAnimal–TopViewMouse) bodyparts.

Verified against Test 27 SA-TVM H5 bodypart list. See INFO_of_rear_classifier.md.
"""

from __future__ import annotations

from typing import Mapping

# Sturman DLCAnalyzer OFT → SA-TVM (this lab)
STURMAN_TO_SA_TVM: Mapping[str, str] = {
    "nose": "nose",
    "headcentre": "head_midpoint",
    "neck": "neck",
    "bodycentre": "mouse_center",
    "bcl": "left_midside",
    "bcr": "right_midside",
    "hipl": "left_hip",
    "hipr": "right_hip",
    "earl": "left_ear",
    "earr": "right_ear",
    "tailbase": "tail_base",
    "tailcentre": "tail2",
    "tailtip": "tail_end",
}

# Ordered unique SA-TVM parts required for the 22-D skeleton
SA_TVM_PARTS: tuple[str, ...] = (
    "nose",
    "head_midpoint",
    "neck",
    "mouse_center",
    "left_midside",
    "right_midside",
    "left_hip",
    "right_hip",
    "left_ear",
    "right_ear",
    "tail_base",
    "tail2",
    "tail_end",
)

# Optional knobs (defaults match INFO)
DEFAULT_BODY_PART = "mouse_center"
DEFAULT_TAIL_MID_PART = "tail2"
