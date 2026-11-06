"""SA-TVM keypoint subset for keypoint-MoSeq (kpMS) on open-field SuperAnimal tracks.

OEM maze kpMS expects SLEAP ``STANDARD_NODE_NAMES`` (8 anatomical). SuperAnimal
TopViewMouse has 27 parts — use this subset for a first OF MoSeq fit (not the
maze H5 tracking contract).
"""

from __future__ import annotations

# Compact top-view skeleton: head–trunk–hips–tail (no ear tips / eyes / multi-tail).
SA_KPMS_BODY_PARTS: tuple[str, ...] = (
    "nose",
    "left_ear",
    "right_ear",
    "neck",
    "mouse_center",
    "left_hip",
    "right_hip",
    "tail_base",
    "tail_end",
)

SA_KPMS_EDGES: tuple[tuple[str, str], ...] = (
    ("nose", "left_ear"),
    ("nose", "right_ear"),
    ("nose", "neck"),
    ("neck", "mouse_center"),
    ("mouse_center", "left_hip"),
    ("mouse_center", "right_hip"),
    ("mouse_center", "tail_base"),
    ("tail_base", "tail_end"),
)
