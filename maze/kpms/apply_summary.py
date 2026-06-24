"""Load kpMS preprocess settings from apply sidecars."""

from __future__ import annotations

import json
from pathlib import Path

from .preprocess import KpmsPreprocessConfig


def preprocess_config_from_summary_dict(raw: object) -> KpmsPreprocessConfig | None:
    if not isinstance(raw, dict):
        return None
    db_raw = raw.get("db_path")
    db_path = Path(str(db_raw)) if db_raw else None
    try:
        return KpmsPreprocessConfig(
            min_fragment_frames=int(raw.get("min_fragment_frames", 4)),
            jump_filter_cm=float(raw.get("jump_filter_cm", 15.0)),
            jump_filter_lookahead_frames=int(raw.get("jump_filter_lookahead_frames", 3)),
            px_per_cm=float(raw.get("px_per_cm", 2.42)),
            retain_all_frames=bool(raw.get("retain_all_frames", False)),
            db_path=db_path,
            pose_stream=raw.get("pose_stream", "anatomical"),
        )
    except (TypeError, ValueError):
        return None


def preprocess_config_from_apply_summary(results_h5: Path) -> KpmsPreprocessConfig | None:
    """Read ``apply_summary.json`` beside ``results_apply.h5``."""
    summary_path = Path(results_h5).parent / "apply_summary.json"
    if not summary_path.is_file():
        return None
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return preprocess_config_from_summary_dict(data.get("preprocess_config"))


def resolve_tracking_h5_path(
    *,
    kpms_root: Path,
    tracking_h5: Path | None = None,
    legacy_db: Path | None = None,
    preprocess_db_path: Path | None = None,
) -> Path | None:
    """Pick a cohort H5 path for ``tracking/anatomical`` reads (local overrides lab paths)."""
    candidates: list[Path] = []
    for raw in (tracking_h5, preprocess_db_path, legacy_db):
        if raw is not None:
            p = Path(raw)
            if p not in candidates:
                candidates.append(p)
    for p in (
        Path(kpms_root) / "kpms_tracking.h5",
        Path(kpms_root).parent / "kpms_tracking.h5",
    ):
        if p not in candidates:
            candidates.append(p)

    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None
