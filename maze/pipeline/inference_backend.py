"""Pluggable pose backends for Pipeline → Inference (SLEAP-NN first; DLC or others later)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class InferenceBackend(ABC):
    """Run pose estimation on a video; return path to predictions (e.g. ``.slp``)."""

    name: str = "abstract"

    @abstractmethod
    def run(
        self,
        *,
        video_path: Path,
        model_path: Path,
        output_path: Path,
        device: str,
        batch_size: int,
    ) -> Optional[Path]:
        ...


class SleapNnBackend(InferenceBackend):
    """SLEAP-NN ``run_inference`` wrapper."""

    name = "sleap_nn"

    def run(
        self,
        *,
        video_path: Path,
        model_path: Path,
        output_path: Path,
        device: str,
        batch_size: int,
    ) -> Optional[Path]:
        try:
            from sleap_nn.predict import run_inference
        except ImportError:
            return None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        run_inference(
            data_path=str(video_path),
            model_paths=[str(model_path)],
            output_path=str(output_path),
            device=device,
            batch_size=batch_size,
            no_empty_frames=True,
        )
        return output_path if output_path.exists() else None


class DeepLabCutBackendStub(InferenceBackend):
    """Reserved for a future DLC integration (pose path → same headless encode stage)."""

    name = "deeplabcut_stub"

    def run(
        self,
        *,
        video_path: Path,
        model_path: Path,
        output_path: Path,
        device: str,
        batch_size: int,
    ) -> Optional[Path]:
        del video_path, model_path, output_path, device, batch_size
        return None


def get_backend(kind: str) -> InferenceBackend:
    k = (kind or "sleap_nn").strip().lower()
    if k in ("dlc", "deeplabcut", "deeplabcut_stub"):
        return DeepLabCutBackendStub()
    return SleapNnBackend()
