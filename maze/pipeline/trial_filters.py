"""Task-aware manifest filters for shared offline processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from ..core.tasks import ARENA_TYPE_CIRCULAR, ARENA_TYPE_RADIAL_ARM
from .io.file_discovery import TrialManifest
from .trial_quality import detect_trial_data_quality

PrefilterMode = Literal["auto", "controller", "legacy"]


def _is_controller_manifest(manifest: TrialManifest) -> bool:
    """Best-effort check for controller-origin trials stored directly in results H5."""
    raw = str(getattr(manifest, "input_h5_path", "") or "").strip()
    return raw in {"", ".", "None"}


@dataclass(frozen=True)
class TrialFilterPolicy:
    """Filtering and mistrial rules for one task's offline manifests."""

    expected_frame_diff: int | None
    quality_check: Callable[[TrialManifest], str | None]


def _shared_quality_checker(
    expected_frame_diff: int | None,
) -> Callable[[TrialManifest], str | None]:
    def check(manifest: TrialManifest) -> str | None:
        return detect_trial_data_quality(
            manifest,
            expected_frame_diff=expected_frame_diff,
        )

    return check


TASK_FILTER_POLICIES: dict[str, TrialFilterPolicy] = {
    ARENA_TYPE_CIRCULAR: TrialFilterPolicy(
        expected_frame_diff=-1,
        quality_check=_shared_quality_checker(-1),
    ),
    ARENA_TYPE_RADIAL_ARM: TrialFilterPolicy(
        expected_frame_diff=None,
        quality_check=_shared_quality_checker(None),
    ),
}


def policy_for_arena(arena_type: str) -> TrialFilterPolicy:
    """Return the manifest policy for ``arena_type`` with a safe shared fallback."""
    return TASK_FILTER_POLICIES.get(
        arena_type,
        TrialFilterPolicy(
            expected_frame_diff=None,
            quality_check=_shared_quality_checker(None),
        ),
    )


def expected_frame_diff(arena_type: str) -> int | None:
    """Return the enforced frame delta for the task, if any."""
    return policy_for_arena(arena_type).expected_frame_diff


def trial_matches_frame_policy(
    manifest: TrialManifest,
    arena_type: str,
    *,
    mode: PrefilterMode = "auto",
) -> bool:
    """Return whether the manifest matches the task's frame-count policy."""
    if mode == "controller":
        return True
    if mode == "auto" and _is_controller_manifest(manifest):
        return True
    diff = expected_frame_diff(arena_type)
    if diff is None:
        return True
    if manifest.h5_n_frames is None or manifest.video_n_frames is None:
        return False
    return (manifest.video_n_frames - manifest.h5_n_frames) == diff


def detect_task_mistrial(
    manifest: TrialManifest,
    arena_type: str,
    *,
    mode: PrefilterMode = "auto",
) -> str | None:
    """Run the task-specific data-quality check for one manifest."""
    if mode == "controller":
        return None
    if mode == "auto" and _is_controller_manifest(manifest):
        return None
    return policy_for_arena(arena_type).quality_check(manifest)
