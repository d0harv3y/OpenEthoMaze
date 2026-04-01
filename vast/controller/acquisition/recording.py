"""
Per-trial video and H5 recording (Option B output schema).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Literal, Optional, Tuple, Union

# Return type for on_video_path_conflict callback: overwrite, discard, or keep_both with suffix.
VideoPathConflictChoice = Union[
    Literal["overwrite"],
    Literal["discard"],
    Tuple[Literal["keep_both"], str],
]

import numpy as np

from .config import ControllerConfig
from vast.core.schema import XY_ROW_DTYPE, FEEDBACK_ROW_DTYPE
from vast.core.storage import open_db, write_feedback_table, write_xy_table
from .h5_writer import (
    init_database,
    ensure_trial_group,
    write_animal_label,
    write_trial_settings,
    write_video_meta,
)

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


@dataclass
class XYRow:
    """One row of xy table (built during trial). trial_state is 'iti' | 'wait' | 'run'."""
    frame_index: int
    t_s: float
    x: float
    y: float
    spot_x: float
    spot_y: float
    in_range_x: float
    in_range_y: float
    centroid_x: float
    centroid_y: float
    dist_to_exit_px: float
    trial_state: str  # "iti" | "wait" | "run"
    in_exit_zone: bool
    valid: bool
    is_moving: bool = False


class TrialRecorder:
    """Record one trial: video file + append to H5."""

    def __init__(
        self,
        output_dir: Path,
        db_path: Path,
        animal_id: str,
        session_id: str,
        trial: str,
        config: ControllerConfig,
        run_mode: str = "habituation",
        video_fourcc: str = "mp4v",
    ):
        self.output_dir = Path(output_dir)
        self.db_path = Path(db_path)
        self.animal_id = animal_id
        self.session_id = session_id
        self.trial = trial
        self.config = config
        self.run_mode = run_mode
        self.video_fourcc = video_fourcc
        self._video_writer: Optional[cv2.VideoWriter] = None
        self._video_path: Optional[Path] = None  # final path (for H5 and return)
        self._video_path_temp: Optional[Path] = None  # path written to during recording
        self._frames: List[np.ndarray] = []
        self._xy_rows: List[XYRow] = []
        self._duty_w: List[float] = []
        self._duty_m: List[float] = []
        self._start_time: Optional[float] = None
        self._fps: float = 30.0

    def start(self, frame_shape: tuple, fps: float = 30.0) -> Optional[Path]:
        """Start recording; return final video path. Writes to a temp file until stop() to avoid duplicate/partial-file issues (e.g. preview).
        Tries avc1 first (best for browser/Cursor preview); falls back to mp4v with no error if avc1 fails (e.g. OpenH264 missing). No extra installs.
        """
        if not HAS_CV2:
            return None
        self._fps = fps
        self._start_time = time.monotonic()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        base = f"{self.animal_id}_{self.session_id}_{self.trial}"
        self._video_path = self.output_dir / f"{base}.mp4"
        self._video_path_temp = self.output_dir / f"{base}_recording.mp4"
        h, w = frame_shape[0], frame_shape[1]
        # Try avc1 first for best preview compatibility; fall back to configured codec (usually mp4v) if unavailable.
        for codec in ("avc1", self.video_fourcc):
            fourcc = cv2.VideoWriter_fourcc(*codec)
            # Suppress OpenH264/FFmpeg stderr when trying avc1 so the user doesn't see "Failed to load OpenH264" etc.
            if codec == "avc1":
                try:
                    devnull = os.open(os.devnull, os.O_WRONLY)
                    old_stderr = os.dup(2)
                    os.dup2(devnull, 2)
                except OSError:
                    devnull = old_stderr = None
            self._video_writer = cv2.VideoWriter(
                str(self._video_path_temp), fourcc, fps, (int(w), int(h)), True
            )
            if codec == "avc1" and devnull is not None:
                try:
                    os.dup2(old_stderr, 2)
                    os.close(devnull)
                except OSError:
                    pass
            if self._video_writer is not None and self._video_writer.isOpened():
                break
            if self._video_writer is not None:
                self._video_writer.release()
                self._video_writer = None
        if self._video_writer is None:
            fourcc = cv2.VideoWriter_fourcc(*self.video_fourcc)
            self._video_writer = cv2.VideoWriter(
                str(self._video_path_temp), fourcc, fps, (int(w), int(h)), True
            )
        return self._video_path

    def write_frame(
        self,
        image: np.ndarray,
        frame_index: int,
        x_px: float,
        y_px: float,
        dist_to_exit_px: float,
        trial_state: str,
        in_exit_zone: bool,
        valid: bool,
        duty_pct: float,
        spot_xy: Optional[Tuple[float, float]] = None,
        in_range_xy: Optional[Tuple[float, float]] = None,
        centroid_xy: Optional[Tuple[float, float]] = None,
    ) -> None:
        if self._video_writer is not None:
            if image.ndim == 2:
                image = np.stack([image] * 3, axis=-1)
            self._video_writer.write(image)
        if self._start_time is None:
            self._start_time = time.monotonic()
        t_s = time.monotonic() - self._start_time
        self._xy_rows.append(
            XYRow(
                frame_index=frame_index,
                t_s=t_s,
                x=x_px, y=y_px,
                spot_x=float(spot_xy[0]) if spot_xy is not None else np.nan,
                spot_y=float(spot_xy[1]) if spot_xy is not None else np.nan,
                in_range_x=float(in_range_xy[0]) if in_range_xy is not None else np.nan,
                in_range_y=float(in_range_xy[1]) if in_range_xy is not None else np.nan,
                centroid_x=float(centroid_xy[0]) if centroid_xy is not None else np.nan,
                centroid_y=float(centroid_xy[1]) if centroid_xy is not None else np.nan,
                dist_to_exit_px=dist_to_exit_px,
                trial_state=trial_state,
                in_exit_zone=in_exit_zone,
                valid=valid,
            )
        )
        self._duty_w.append(duty_pct)
        self._duty_m.append(duty_pct)

    def cancel(self, delete_video: bool = True) -> None:
        """Release video writer and discard in-memory data without writing H5. Optionally delete the partial video file."""
        if self._video_writer is not None:
            self._video_writer.release()
            self._video_writer = None
        if delete_video and self._video_path_temp is not None and self._video_path_temp.exists():
            try:
                self._video_path_temp.unlink()
            except Exception:
                pass
        self._video_path_temp = None
        self._video_path = None
        self._xy_rows = []
        self._duty_w = []
        self._duty_m = []

    def stop(
        self,
        exit_x_px: float,
        exit_y_px: float,
        timestamp_str: Optional[str] = None,
        on_video_path_conflict: Optional[
            Callable[[Path], VideoPathConflictChoice]
        ] = None,
        conflict_choice: Optional[VideoPathConflictChoice] = None,
    ) -> None:
        """Flush video and write H5 trial group. If conflict_choice is set, use it for video path conflict instead of calling on_video_path_conflict."""
        if self._video_writer is not None:
            self._video_writer.release()
            self._video_writer = None
        if self._video_path_temp is not None and self._video_path_temp.exists():
            if self._video_path is not None:
                choice = None
                if self._video_path.exists():
                    choice = conflict_choice if conflict_choice is not None else (
                        on_video_path_conflict(self._video_path)
                        if on_video_path_conflict is not None
                        else None
                    )
                elif conflict_choice is not None and conflict_choice not in ("overwrite", "discard"):
                    # keep_both from merged dialog when only H5 conflicted; still save video to new trial path
                    choice = conflict_choice
                if choice == "discard":
                    try:
                        self._video_path_temp.unlink()
                    except Exception:
                        pass
                    self._video_path = None
                elif choice == "overwrite":
                    self._video_path_temp.replace(self._video_path)
                elif choice is not None:
                        # keep_both: caller already updated self.trial (e.g. + "(2)"); use current path
                    new_path = self.output_dir / f"{self.animal_id}_{self.session_id}_{self.trial}.mp4"
                    self._video_path_temp.replace(new_path)
                    self._video_path = new_path
                else:
                    self._video_path_temp.replace(self._video_path)
        self._video_path_temp = None
        init_database(self.db_path)
        run_phase = self.config.run_phase or "habituation"
        run_mode = self.config.run_mode or "continuous"
        with open_db(self.db_path, "a") as h5:
            animal_meta = next(
                (a for a in self.config.session.animals if str(a.animal_id) == str(self.animal_id)),
                None,
            )
            if animal_meta is not None:
                write_animal_label(
                    h5,
                    self.animal_id,
                    sex=animal_meta.sex,
                    tx=animal_meta.tx,
                    strain=animal_meta.strain,
                    experiment=None,
                    researcher=None,
                    drug=animal_meta.drug,
                    notes=animal_meta.notes,
                )
            g = ensure_trial_group(
                h5,
                self.animal_id,
                self.session_id,
                self.trial,
                video_path=str(self._video_path) if self._video_path else None,
                sleap_path=None,
                run_phase=run_phase,
                run_mode=run_mode,
            )
            arena = self.config.arena
            # Align pipeline band splitting with controller state labels.
            # Use the first recorded frame whose state is "run" as trial_start_frame.
            # This keeps controller and legacy processing on the same pipeline path.
            trial_start_frame = 0
            for i, row in enumerate(self._xy_rows):
                if (row.trial_state or "").strip().lower() == "run":
                    trial_start_frame = i
                    break
            write_trial_settings(
                g,
                arena_radius_px=arena.radius_px,
                px_per_cm=arena.px_per_cm,
                arena_center_x_px=arena.arena_center_x_px,
                arena_center_y_px=arena.arena_center_y_px,
                timestamp=timestamp_str,
                phase=run_phase,
                run_mode=run_mode,
                exit_x=exit_x_px,
                exit_y=exit_y_px,
                trial_start_frame=trial_start_frame,
            )
            n = len(self._xy_rows)
            duration_s = self._xy_rows[-1].t_s if self._xy_rows else 0.0
            write_video_meta(g, self._fps, n, duration_s)
            if self._xy_rows:
                arr_spot = np.zeros(n, dtype=XY_ROW_DTYPE)
                arr_in_range = np.zeros(n, dtype=XY_ROW_DTYPE)
                arr_centroid = np.zeros(n, dtype=XY_ROW_DTYPE)
                for i, r in enumerate(self._xy_rows):
                    # Shared per-frame metadata
                    for arr in (arr_spot, arr_in_range, arr_centroid):
                        arr[i]["frame_index"] = r.frame_index
                        arr[i]["t_s"] = r.t_s
                        arr[i]["dist_to_exit_px"] = r.dist_to_exit_px
                        arr[i]["trial_state"] = r.trial_state.encode("utf-8")
                        arr[i]["in_exit_zone"] = 1 if r.in_exit_zone else 0
                        arr[i]["is_moving"] = 1 if r.is_moving else 0

                    # Point-specific coordinates/validity
                    arr_spot[i]["x"] = r.spot_x
                    arr_spot[i]["y"] = r.spot_y
                    arr_spot[i]["valid"] = 1 if (np.isfinite(r.spot_x) and np.isfinite(r.spot_y)) else 0

                    arr_in_range[i]["x"] = r.in_range_x
                    arr_in_range[i]["y"] = r.in_range_y
                    arr_in_range[i]["valid"] = 1 if (np.isfinite(r.in_range_x) and np.isfinite(r.in_range_y)) else 0

                    arr_centroid[i]["x"] = r.centroid_x
                    arr_centroid[i]["y"] = r.centroid_y
                    arr_centroid[i]["valid"] = 1 if (np.isfinite(r.centroid_x) and np.isfinite(r.centroid_y)) else 0

                write_xy_table(g, "spot", arr_spot, self._fps)
                write_xy_table(g, "in-range", arr_in_range, self._fps)
                write_xy_table(g, "centroid", arr_centroid, self._fps)
                # Unified per-frame feedback table (frame_index, trial_state, motor_fb, light_fb, sound_fb).
                fb = np.zeros(n, dtype=FEEDBACK_ROW_DTYPE)
                for i, r in enumerate(self._xy_rows):
                    fb[i]["frame_index"] = r.frame_index
                    fb[i]["trial_state"] = r.trial_state.encode("utf-8")
                    # For now, motor feedback is the duty cycle; light/sound are unused (0).
                    duty = float(self._duty_m[i]) if i < len(self._duty_m) else 0.0
                    fb[i]["motor_fb"] = duty
                    fb[i]["light_fb"] = 0.0
                    fb[i]["sound_fb"] = 0.0
                write_feedback_table(g, fb)
            else:
                # If no frames were recorded, ensure any previous feedback data is cleared.
                if "feedback" in g:
                    del g["feedback"]
