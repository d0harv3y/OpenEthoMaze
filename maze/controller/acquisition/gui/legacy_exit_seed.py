"""Legacy exit XY seeding for VAST virtual trials (H5 path heuristics)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ..h5_writer import open_db
from .identity import parse_virtual_video_identity

if TYPE_CHECKING:
    from .main_window import MainWindow


def legacy_h5_candidate_paths(
    *,
    virtual_video_path: Path,
    seed_legacy_source: str,
    h5_filename: str,
    output_dir: str,
) -> list[Path]:
    """
    Resolve candidate legacy trial HDF5 paths for virtual-video exit lookup.

    Order: explicit ``seed_legacy_source``, then ``<video>/../<h5_filename>``,
    ``<video>/../trials.h5``, then ``<output_dir>/<h5_filename>`` when configured.
    """
    explicit_legacy_db = (seed_legacy_source or "").strip()
    if explicit_legacy_db:
        return [Path(explicit_legacy_db)]
    base_dir = virtual_video_path.parent.parent
    h5_name = h5_filename or "trials.h5"
    candidates = [
        base_dir / h5_name,
        base_dir / "trials.h5",
    ]
    if output_dir:
        candidates.append(Path(output_dir) / h5_name)
    return candidates


def _lookup_legacy_exit_in_h5(
    legacy_db_path: Path,
    animal_id: str,
    session_id: str,
    trial: str,
) -> tuple[Optional[tuple[float, float]], str]:
    """Load exit_x/exit_y from an existing legacy H5 trial group; return coords and status text."""
    with open_db(legacy_db_path, "r") as h5:
        grp_path = f"/{animal_id}/{session_id}/{trial}"
        if grp_path not in h5:
            return None, "Legacy exit lookup: trial not found; using computed exit."
        g_trial = h5[grp_path]
        if "exit_x" not in g_trial.attrs or "exit_y" not in g_trial.attrs:
            return None, "Legacy exit lookup: exit_x/exit_y missing; using computed exit."
        exit_x = float(g_trial.attrs["exit_x"])
        exit_y = float(g_trial.attrs["exit_y"])
        loaded_exit_idx = None
        for key_name in ("exit_angle_index", "exit_idx", "exit_index"):
            if key_name in g_trial.attrs:
                try:
                    loaded_exit_idx = int(g_trial.attrs[key_name]) + 1
                except Exception:
                    loaded_exit_idx = None
                break
        if loaded_exit_idx is not None:
            status = (
                f"Legacy exit lookup: loaded from {legacy_db_path} "
                f"(exit #{loaded_exit_idx})."
            )
        else:
            status = f"Legacy exit lookup: loaded from {legacy_db_path}."
        return (exit_x, exit_y), status


def seed_legacy_exit_for_virtual_start(window: MainWindow) -> Optional[str]:
    """
    When VAST virtual mode uses legacy session seed (-1), copy exit_x/exit_y from the
    legacy H5 trial matching the selected virtual video name.

    Returns a status-bar message when lookup runs; ``None`` when this path does not apply.
    """
    if not (
        window._task_mode == "vast"
        and window._camera_source.currentText().startswith("Virtual")
        and window._config.session.seed_mode == "legacy"
        and window._virtual_video_path is not None
    ):
        return None

    window._trial_controller.clear_legacy_exit_xy()
    try:
        parsed = parse_virtual_video_identity(window._virtual_video_path.stem)
        if parsed is None:
            return "Legacy exit lookup: couldn't parse video name; using computed exit."
        animal_id, session_id, trial = parsed
        candidates = legacy_h5_candidate_paths(
            virtual_video_path=window._virtual_video_path,
            seed_legacy_source=window._config.session.seed_legacy_source or "",
            h5_filename=window._config.h5_filename or "trials.h5",
            output_dir=window._config.output_dir or "",
        )
        legacy_db_path = next((p for p in candidates if p.exists()), None)
        if legacy_db_path is None:
            return "Legacy exit lookup: H5 not found; using computed exit."
        coords, status = _lookup_legacy_exit_in_h5(
            legacy_db_path, animal_id, session_id, trial
        )
        if coords is not None:
            window._trial_controller.set_legacy_exit_xy(coords[0], coords[1])
        return status
    except Exception as e:
        return f"Legacy exit lookup failed ({e}); using computed exit."
