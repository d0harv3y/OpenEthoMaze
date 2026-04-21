"""Load ehram ``ehram_results.h5`` global maze template as pixel polylines for unified overlay.

ehram stores the shared template under ``/metadata/global_template`` (``center_poly_xy``,
``arms_table``, ``escape_holes``), not under ORM's ``task_data/radial_arm``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import h5py
import numpy as np

from maze.pipeline.db.trial_key import TrialKey


def _decode_attr(val: Any) -> Any:
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


def _circle_poly(cx: float, cy: float, r: float, n: int = 48) -> np.ndarray:
    """Closed polygon approximating a circle (for ``cv2.polylines``)."""
    rr = max(float(r), 1e-6)
    t = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False, dtype=np.float64)
    return np.stack([cx + rr * np.cos(t), cy + rr * np.sin(t)], axis=-1)


def load_ehram_global_template_polygons_px(
    pipeline_db: Path,
    key: TrialKey,
) -> Optional[dict[str, np.ndarray]]:
    """
    Build region polylines from ``/metadata/global_template`` + trial ``escape_arm``.

    Region names mirror ORM RAM overlays: ``center``, ``arm{i}_front`` / ``arm{i}_back``,
    and ``hole`` (circle sampled from ``escape_holes/arm_{k}`` as x, y, radius px).
    """
    path = Path(pipeline_db)
    if not path.is_file():
        return None
    try:
        with h5py.File(str(path), "r") as h5:
            if "metadata" not in h5 or "global_template" not in h5["metadata"]:
                return None
            g = h5["metadata"]["global_template"]
            if "arms_table" not in g or "center_poly_xy" not in g.attrs:
                return None

            center_poly = np.asarray(
                json.loads(str(_decode_attr(g.attrs["center_poly_xy"]))),
                dtype=np.float64,
            )
            if center_poly.ndim != 2 or center_poly.shape[1] != 2 or center_poly.shape[0] < 3:
                return None

            arms_table = np.asarray(g["arms_table"][:])
            out: dict[str, np.ndarray] = {"center": center_poly}

            for i in range(len(arms_table)):
                row = arms_table[i]
                ai = int(row["arm_index"])
                hi = int(row["half_index"])
                half = "front" if hi == 0 else "back"
                name = f"arm{ai}_{half}"
                pts = np.array(
                    [
                        [float(row["x0"]), float(row["y0"])],
                        [float(row["x1"]), float(row["y1"])],
                        [float(row["x2"]), float(row["y2"])],
                        [float(row["x3"]), float(row["y3"])],
                    ],
                    dtype=np.float64,
                )
                out[name] = pts

            aid = str(key.animal_id)
            phase = str(key.session)
            trial = str(key.trial)
            if aid not in h5 or phase not in h5[aid] or trial not in h5[aid][phase]:
                return out
            g_trial = h5[aid][phase][trial]
            raw_ea = g_trial.attrs.get("escape_arm", -1)
            try:
                escape_arm = int(_decode_attr(raw_ea) if raw_ea is not None else -1)
            except (TypeError, ValueError):
                escape_arm = -1
            if escape_arm < 0 or escape_arm > 7:
                escape_arm = 0

            if "escape_holes" in g:
                eh = g["escape_holes"]
                arm_key = f"arm_{escape_arm}"
                if arm_key in eh:
                    xyr = np.asarray(eh[arm_key][:], dtype=np.float64).ravel()
                    if xyr.size >= 3:
                        cx, cy, r = float(xyr[0]), float(xyr[1]), float(xyr[2])
                        out["hole"] = _circle_poly(cx, cy, r)

            return out
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
