"""
Debug why a specific trial has no QC composite image.

Usage:
    uv run python scripts/debug_qc_trial.py [animal_id] [session] [trial]
    uv run python scripts/debug_qc_trial.py 5416 S01 T01
    uv run python scripts/debug_qc_trial.py 5416 experimental S01 T01  (phase optional)

Prints: trial group existence, attrs (exit_x, exit_y, arena, etc.), qc_images contents.
If composite is missing, attempts to generate it with full traceback.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from vast_pipeline.config import OUTPUT_H5
from vast_pipeline.storage.h5_db import TrialKey, open_db, read_trial_settings, read_xy_table, read_qc_image


def _find_trial_path(h5, animal_id: str, phase: str) -> tuple[str, str] | None:
    """Return (session, trial) for first matching animal/phase, or None."""
    if animal_id not in h5:
        return None
    g_animal = h5[animal_id]
    if phase not in g_animal:
        return None
    g_phase = g_animal[phase]
    for session in g_phase.keys():
        g_session = g_phase[session]
        for trial in g_session.keys():
            return (session, trial)
    return None


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    animal_id = args[0] if len(args) > 0 else "5416"
    if len(args) >= 4:
        phase = args[1]
        session = args[2]
        trial = args[3]
    elif len(args) >= 3:
        phase = "experimental"
        session = args[1]
        trial = args[2]
    else:
        phase = "experimental"
        session = "S01"
        trial = "T01"

    db_path = OUTPUT_H5
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        sys.exit(1)

    key = TrialKey(animal_id=animal_id, phase=phase, session=session, trial=trial)
    path_str = key.path()
    print(f"Trial key: {path_str}")
    print(f"DB: {db_path}\n")

    with open_db(db_path, "r") as h5:
        if path_str not in h5:
            # Try alternate case
            alt = TrialKey(animal_id=animal_id, phase=phase, session=session.upper() if len(session) == 3 else session, trial=trial.upper() if len(trial) == 3 else trial)
            if alt.path() != path_str and alt.path() in h5:
                print(f"Found with different case: {alt.path()}")
                key = alt
                path_str = key.path()
            else:
                print(f"Trial group not found: {path_str}")
                print("Available under animal/phase:")
                if animal_id in h5:
                    for ph in h5[animal_id].keys():
                        for sess in h5[animal_id][ph].keys():
                            for t in h5[animal_id][ph][sess].keys():
                                print(f"  /{animal_id}/{ph}/{sess}/{t}")
                sys.exit(1)

        g_trial = h5[path_str]
        print("Attrs:")
        for k in sorted(g_trial.attrs.keys()):
            v = g_trial.attrs[k]
            if isinstance(v, bytes):
                v = v.decode("utf-8", errors="replace")
            print(f"  {k}: {v}")
        print("\nSubgroups:")
        for name in g_trial.keys():
            print(f"  {name}/")
            if name == "qc_images":
                for qname in g_trial[name].keys():
                    print(f"    {qname}")
            if name == "ambulation_metrics":
                for pname in g_trial[name].keys():
                    print(f"    {pname}/")

    # Read settings (from DB)
    settings = None
    h5_fps = None
    try:
        settings, h5_fps, _trial_start_frame = read_trial_settings(db_path, key)
        print("\nSettings (from DB):")
        print(f"  arena_center_x_px={settings.arena_center_x_px}, arena_center_y_px={settings.arena_center_y_px}")
        print(f"  arena_radius_px={settings.arena_radius_px}, px_per_cm={settings.px_per_cm}")
        print(f"  exit_x={settings.exit_x}, exit_y={settings.exit_y}")
        print(f"  exit_pos={settings.exit_pos}")
        print(f"  h5_fps={h5_fps}")
        if settings.arena_radius_px is not None and settings.arena_radius_px <= 0:
            print("  >>> arena_radius_px is 0 or negative — QC will fail (scale division).")
        if settings.exit_pos is None:
            print("  >>> exit_pos is None — pipeline skips metrics and QC for this trial.")
    except Exception as e:
        print(f"\nFailed to read trial settings: {e}")
        import traceback
        traceback.print_exc()

    # Check for composite
    composite = read_qc_image(db_path, key, "composite")
    if composite is not None:
        print(f"\nQC composite: present, shape {composite.shape}")
        sys.exit(0)

    print("\nQC composite: MISSING. Attempting to generate with full traceback...")
    if settings is None or settings.exit_pos is None:
        print("  Cannot generate: no settings or exit_pos.")
        sys.exit(1)
    xy = read_xy_table(db_path, key, "spot")
    if xy is None:
        print("  No ambulation_metrics/spot/xy — trial may not have been processed with SLEAP, or exit_pos was None.")
        sys.exit(1)
    xy_arr = np.column_stack([xy["x"], xy["y"]])
    valid_arr = (xy["valid"] != 0)
    fps = float(h5_fps) if h5_fps and h5_fps > 0 else 30.0
    try:
        from vast_pipeline.viz.qc_images import generate_trial_qc_images
        generate_trial_qc_images(
            db_path=db_path,
            key=key,
            xy=xy_arr,
            valid=valid_arr,
            exit_pos=settings.exit_pos,
            arena_center_x_px=settings.arena_center_x_px,
            arena_center_y_px=settings.arena_center_y_px,
            arena_radius_px=settings.arena_radius_px,
            px_per_cm=settings.px_per_cm,
            fps=fps,
        )
        print("  Generation completed. Check qc_images/composite again.")
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
