"""Train / predict Sturman-style rearing MLP (torch)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from of_rear_classifier.labels import CLASS_NAMES, DEFAULT_CLASS
from of_rear_classifier.mlp import DEFAULT_BATCH_SIZE, DEFAULT_EPOCHS, MlpSpec, build_torch_mlp
from of_rear_classifier.window import DEFAULT_INTEGRATION_WINDOW, stack_centered

# Softmax order (index = class id)
CLASS_TO_IDX = {name: i for i, name in enumerate(CLASS_NAMES)}


@dataclass
class TrainResult:
    model: object
    train_acc: float
    n_train: int
    class_names: tuple[str, ...]


def encode_labels(y: np.ndarray) -> np.ndarray:
    out = np.empty(len(y), dtype=np.int64)
    for i, lab in enumerate(y):
        out[i] = CLASS_TO_IDX.get(str(lab), CLASS_TO_IDX[DEFAULT_CLASS])
    return out


def subsample_training(
    x: np.ndarray,
    y: np.ndarray,
    *,
    seed: int = 0,
    none_ratio: float = 2.0,
    max_train: int | None = 80_000,
) -> tuple[np.ndarray, np.ndarray]:
    """Keep all behavior frames; cap ``None`` at ``none_ratio`` × behavior count; optional max_train."""
    y = np.asarray(y)
    x = np.asarray(x)
    beh = y != DEFAULT_CLASS
    n_beh = int(np.sum(beh))
    none_idx = np.flatnonzero(~beh)
    beh_idx = np.flatnonzero(beh)
    rng = np.random.default_rng(seed)
    n_none_keep = min(len(none_idx), int(none_ratio * max(n_beh, 1)))
    keep_none = rng.choice(none_idx, size=n_none_keep, replace=False) if n_none_keep else np.array([], dtype=int)
    keep = np.concatenate([beh_idx, keep_none])
    if max_train is not None and len(keep) > max_train:
        keep = rng.choice(keep, size=max_train, replace=False)
    rng.shuffle(keep)
    return x[keep], y[keep]


def train_mlp(
    x: np.ndarray,
    y: np.ndarray,
    *,
    epochs: int = DEFAULT_EPOCHS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    lr: float = 1e-3,
    seed: int = 0,
    device: str | None = None,
    none_ratio: float = 2.0,
    max_train: int | None = 80_000,
) -> TrainResult:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    x, y = subsample_training(x, y, seed=seed, none_ratio=none_ratio, max_train=max_train)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(y))
    x = np.asarray(x, dtype=np.float32)[order]
    y_idx = encode_labels(np.asarray(y))[order]

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    dev = torch.device(device)

    spec = MlpSpec(n_in=x.shape[1], n_classes=len(CLASS_NAMES))
    model = build_torch_mlp(spec).to(dev)
    opt = torch.optim.RMSprop(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()

    xt = torch.from_numpy(x).to(dev)
    yt = torch.from_numpy(y_idx).to(dev)
    ds = TensorDataset(xt, yt)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True)

    model.train()
    for _ in range(epochs):
        for xb, yb in loader:
            opt.zero_grad(set_to_none=True)
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()

    model.eval()
    with torch.no_grad():
        logits = model(xt)
        pred = logits.argmax(dim=1).cpu().numpy()
    acc = float(np.mean(pred == y_idx))
    return TrainResult(model=model, train_acc=acc, n_train=len(y_idx), class_names=CLASS_NAMES)

def predict_classes(model, x: np.ndarray, *, device: str | None = None) -> np.ndarray:
    import torch

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    dev = torch.device(device)
    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(np.asarray(x, dtype=np.float32)).to(dev))
        pred = logits.argmax(dim=1).cpu().numpy()
    return np.asarray(CLASS_NAMES)[pred]


def predict_proba(model, x: np.ndarray, *, device: str | None = None) -> np.ndarray:
    """Softmax probabilities ``(N, n_classes)`` in ``CLASS_NAMES`` order."""
    import torch
    from torch.nn import functional as F

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    dev = torch.device(device)
    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(np.asarray(x, dtype=np.float32)).to(dev))
        return F.softmax(logits, dim=1).cpu().numpy()


def features_to_window_xy(
    features_z: np.ndarray,
    frame_labels: np.ndarray,
    *,
    integration_window: int = DEFAULT_INTEGRATION_WINDOW,
) -> tuple[np.ndarray, np.ndarray]:
    x, y = stack_centered(features_z, integration_window=integration_window, labels=frame_labels)
    assert y is not None
    return x, y
