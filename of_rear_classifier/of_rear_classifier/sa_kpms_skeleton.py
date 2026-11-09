"""SA-TVM keypoint subset for keypoint-MoSeq (kpMS) on open-field SuperAnimal tracks.

Same **13** parts as the Sturman→ReLU skeleton features (``parts_map.SA_TVM_PARTS``).
OEM maze kpMS still expects SLEAP ``STANDARD_NODE_NAMES`` (8 anatomical) — this
OF path stays under ``of_rear_classifier/`` until promoted.
"""

from __future__ import annotations

from of_rear_classifier.parts_map import SA_TVM_PARTS

# Alias: keep one source of truth with the MLP feature map.
SA_KPMS_BODY_PARTS: tuple[str, ...] = SA_TVM_PARTS
assert len(SA_KPMS_BODY_PARTS) == 13

# Edges ≈ Sturman ``create_skeleton_v1`` length segments (S1–S10) + ear spokes.
SA_KPMS_EDGES: tuple[tuple[str, str], ...] = (
    ("nose", "head_midpoint"),  # S1
    ("head_midpoint", "neck"),  # S2
    ("neck", "mouse_center"),  # S3
    ("mouse_center", "right_midside"),  # S4
    ("mouse_center", "left_midside"),  # S5
    ("mouse_center", "tail_base"),  # S6
    ("tail_base", "right_hip"),  # S7
    ("tail_base", "left_hip"),  # S8
    ("tail_base", "tail2"),  # S9
    ("tail2", "tail_end"),  # S10
    ("nose", "left_ear"),
    ("nose", "right_ear"),
)
