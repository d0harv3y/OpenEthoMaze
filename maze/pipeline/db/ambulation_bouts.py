from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

from ._shared import ensure_group, open_db
from .trial_key import TrialKey


def _encode_trial_state(state: Any) -> bytes:
    raw = str(state or "run").strip().lower().encode("utf-8")[:16]
    return raw.ljust(16, b"\0")


def movement_bout_dtype() -> np.dtype:
    """Structured dtype for movement bout data."""
    return np.dtype(
        [
            ("start_frame", np.int32),
            ("end_frame", np.int32),
            ("duration_frames", np.int32),
            ("duration_s", np.float32),
            ("total_distance_m", np.float32),
            ("mean_speed_mps", np.float32),
            ("max_speed_mps", np.float32),
            ("trial_state", "S16"),
        ]
    )


def write_movement_bouts(
    db_path: Optional[Path],
    key: TrialKey,
    point_name: str,
    bouts: list[dict[str, Any]],
    analysis_start_frame: int = 0,
) -> None:
    """Write movement bouts, converting to video-frame coordinates."""
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_amb = ensure_group(g_trial, "ambulation_metrics")
        g_pt = ensure_group(g_amb, point_name)
        if not bouts:
            if "movement_bouts" in g_pt:
                del g_pt["movement_bouts"]
            g_pt.create_dataset(
                "movement_bouts",
                data=np.array([], dtype=movement_bout_dtype()),
                compression="gzip",
            )
            g_pt.attrs["analysis_start_frame"] = int(analysis_start_frame)
            return

        bout_array = np.zeros((len(bouts),), dtype=movement_bout_dtype())
        for i, bout in enumerate(bouts):
            bout_array[i]["start_frame"] = int(
                analysis_start_frame + bout.get("start_frame", 0)
            )
            bout_array[i]["end_frame"] = int(
                analysis_start_frame + bout.get("end_frame", 0)
            )
            bout_array[i]["duration_frames"] = int(bout.get("duration_frames", 0))
            bout_array[i]["duration_s"] = float(bout.get("duration_s", 0.0))
            bout_array[i]["total_distance_m"] = float(
                bout.get("total_distance_m", 0.0)
            )
            bout_array[i]["mean_speed_mps"] = float(bout.get("mean_speed_mps", 0.0))
            bout_array[i]["max_speed_mps"] = float(bout.get("max_speed_mps", 0.0))
            bout_array[i]["trial_state"] = _encode_trial_state(
                bout.get("trial_state", "run")
            )

        if "movement_bouts" in g_pt:
            del g_pt["movement_bouts"]
        g_pt.create_dataset("movement_bouts", data=bout_array, compression="gzip")
        g_pt.attrs["analysis_start_frame"] = int(analysis_start_frame)
