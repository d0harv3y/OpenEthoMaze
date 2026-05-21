"""Pluggable pose backends for Pipeline → Virtual acquisition (SLEAP-NN first; DLC later)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

BACKEND_KIND_SLEAP_NN = "sleap_nn"
BACKEND_KIND_DEEPLABCUT_STUB = "deeplabcut_stub"

# GUI / CLI labels → kind string for :func:`get_backend`
BACKEND_CHOICES: tuple[tuple[str, str], ...] = (
    ("SLEAP-NN", BACKEND_KIND_SLEAP_NN),
    ("DeepLabCut (not available)", BACKEND_KIND_DEEPLABCUT_STUB),
)


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
    ) -> Optional[Path]: ...


class SleapNnBackend(InferenceBackend):
    """SLEAP-NN ``run_inference`` wrapper."""

    name = BACKEND_KIND_SLEAP_NN

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
        except ImportError as exc:
            raise RuntimeError(
                "sleap-nn is not installed. Install with: uv sync --extra sleap"
            ) from exc
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

    name = BACKEND_KIND_DEEPLABCUT_STUB

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
        raise RuntimeError("DeepLabCut backend is not implemented (stub only).")


def is_sleap_nn_available() -> bool:
    """True when ``sleap_nn`` can be imported (``--extra sleap`` environment)."""
    try:
        import sleap_nn.predict  # noqa: F401
    except ImportError:
        return False
    return True


def planned_slp_output_path(video_path: Path, output_dir: Optional[Path]) -> Path:
    """Default pose file next to video or under ``output_dir`` (``*.predictions.slp``)."""
    name = video_path.with_suffix(".predictions.slp").name
    return (output_dir / name) if output_dir else video_path.with_suffix(".predictions.slp")


def find_existing_pose_output(
    *,
    video_path: Path,
    manifest_sleap: Optional[Path],
    planned_out: Path,
) -> Optional[Path]:
    """
    First existing pose file among manifest DB path, planned output, and video sidecars.

    Used when **skip existing** is enabled in Virtual acquisition: no re-inference, but
    the results H5 ``sleap_path`` / model path are refreshed from the file found.
    """
    candidates: list[Optional[Path]] = [
        manifest_sleap,
        planned_out,
        video_path.with_suffix(".predictions.slp"),
        video_path.with_suffix(".slp"),
    ]
    seen: set[str] = set()
    for p in candidates:
        if p is None:
            continue
        try:
            key = str(p.resolve())
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        if p.exists():
            return p
    return None


def get_backend(kind: str) -> InferenceBackend:
    """
    Resolve a pose backend by kind string.

    Raises:
        ValueError: Unknown *kind* (fail loud; no silent fallback).
    """
    k = (kind or BACKEND_KIND_SLEAP_NN).strip().lower()
    if k in (BACKEND_KIND_SLEAP_NN, "sleap", "sleap-nn"):
        return SleapNnBackend()
    if k in (BACKEND_KIND_DEEPLABCUT_STUB, "dlc", "deeplabcut"):
        return DeepLabCutBackendStub()
    raise ValueError(
        f"Unknown inference backend {kind!r}. "
        f"Supported: {BACKEND_KIND_SLEAP_NN!r}, {BACKEND_KIND_DEEPLABCUT_STUB!r} (stub only)."
    )
