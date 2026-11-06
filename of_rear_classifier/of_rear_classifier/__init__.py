"""Open-field rearing classifier (Sturman / SuperAnimal recipe) — pilot package."""

from __future__ import annotations

__version__ = "0.1.0"

from of_rear_classifier.parts_map import SA_TVM_PARTS, STURMAN_TO_SA_TVM
from of_rear_classifier.skeleton import FEATURE_NAMES, N_FEATURES

__all__ = [
    "FEATURE_NAMES",
    "N_FEATURES",
    "SA_TVM_PARTS",
    "STURMAN_TO_SA_TVM",
    "__version__",
]
