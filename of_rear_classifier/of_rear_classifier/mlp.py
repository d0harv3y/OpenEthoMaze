"""Sturman OFT MLP architecture (Dense 256-ReLU → drop → 128-ReLU → drop → softmax).

Training requires optional ``torch`` (OEM ``uv sync --extra sleap`` or lab). Feature /
window litmus does not import torch.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_HIDDEN = (256, 128)
DEFAULT_DROPOUTS = (0.4, 0.3)
DEFAULT_EPOCHS = 10
DEFAULT_BATCH_SIZE = 32


@dataclass(frozen=True)
class MlpSpec:
    n_in: int
    n_classes: int
    hidden: tuple[int, ...] = DEFAULT_HIDDEN
    dropouts: tuple[float, ...] = DEFAULT_DROPOUTS


def build_torch_mlp(spec: MlpSpec):
    """Return an untrained ``torch.nn.Module``. Raises if torch is missing."""
    try:
        import torch
        from torch import nn
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "torch is required for of_rear_classifier.mlp training; " "uv sync --extra sleap (or install torch)"
        ) from exc

    if len(spec.hidden) != len(spec.dropouts):
        raise ValueError("hidden and dropouts length must match")

    layers: list = []
    prev = spec.n_in
    for units, drop in zip(spec.hidden, spec.dropouts, strict=True):
        layers.append(nn.Linear(prev, units))
        layers.append(nn.ReLU())
        layers.append(nn.Dropout(drop))
        prev = units
    layers.append(nn.Linear(prev, spec.n_classes))
    return nn.Sequential(*layers)
