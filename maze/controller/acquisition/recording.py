"""
Per-trial video and H5 recording (Option B output schema).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Literal, Optional, Sequence, Tuple, Union

import numpy as np

from maze.core.anatomy import BLOB_VERTEX_COUNT
from maze.core.schema import FEEDBACK_ROW_DTYPE, XY_ROW_DTYPE
from maze.core.h5_layout import open_db, write_feedback_table, write_xy_table
from maze.pipeline.tracking_io import AnatomicalTrackingBuffer, BlobTrackingBuffer
from maze.pipeline.video_paths import resolve_video_path, video_path_for_storage

from .shared_config import AcquisitionConfig, FallbackTrackingConfig
from .radial_arm.config import RadialArmControllerConfig
from .region_code import encode_region_code_bytes
from .h5_writer import (
    init_database,
    ensure_trial_group,
    write_animal_label,
    write_trial_settings,
    write_radial_arm_trial_settings,
    write_video_meta,
)

# Return type for on_video_path_conflict callback: overwrite, discard, or keep_both with suffix.
VideoPathConflictChoice = Union[
    Literal["overwrite"],
    Literal["discard"],
    Tuple[Literal["keep_both"], str],
]

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
    region_code: str
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
        config: AcquisitionConfig,
        run_mode: str = "habituation",
        video_fourcc: str = "mp4v",
        seek_to_frame: int = 0,
        virtual_source_video_path: Optional[Path] = None,
        recording_ram_exit_arm_index: Optional[int] = None,
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
        self._seek_to_frame = int(seek_to_frame)
        self._virtual_source_video_path = (
            resolve_video_path(virtual_source_video_path)
            if virtual_source_video_path is not None
            else None
        )
        self._recording_ram_exit_arm_index: Optional[int] = recording_ram_exit_arm_index
        self._anatomical_buffer: Optional[AnatomicalTrackingBuffer] = None
        self._blob_buffer: Optional[BlobTrackingBuffer] = None

    @staticmethod
    def backup_params_json_from_config(config: AcquisitionConfig) -> dict[str, object]:
        """Snapshot fallback-tracker settings for ``tracking/blob`` provenance."""
        ft: FallbackTrackingConfig = config.fallback_tracking
        return {
            "range_low": int(ft.range_low),
            "range_high": int(ft.range_high),
            "min_area": int(ft.min_area),
            "max_area": int(ft.max_area),
            "morph_kernel_size": int(ft.morph_kernel_size),
            "max_jump_px": float(ft.max_jump_px),
            "selection_mode": str(ft.selection_mode),
            "min_circularity": float(ft.min_circularity),
            "max_contours": int(ft.max_contours),
        }

    def _init_blob_capture(self) -> None:
        self._blob_buffer = BlobTrackingBuffer(
            backup_params_json=self.backup_params_json_from_config(self.config),
            blob_source="backup_live",
        )

    def _append_anatomical_pose(
        self,
        frame_index: int,
        pose_xy: np.ndarray,
        pose_scores: Optional[np.ndarray],
        pose_node_valid: Optional[np.ndarray],
        pose_node_names: Sequence[str],
    ) -> None:
        """Buffer one SLEAP pose row (jump-filtered validity from the display path)."""
        xy = np.asarray(pose_xy, dtype=np.float32)
        if xy.ndim != 2 or xy.shape[1] != 2:
            return
        n_nodes = xy.shape[0]
        if n_nodes <= 0 or len(pose_node_names) < n_nodes:
            return

        node_names = tuple(str(pose_node_names[j]) for j in range(n_nodes))
        if self._anatomical_buffer is None:
            self._anatomical_buffer = AnatomicalTrackingBuffer(
                node_names=node_names,
                pose_source="sleap_live",
                fps=self._fps,
                pose_model_path=str(getattr(self.config, "sleap_model_path", "") or "").strip(),
            )
        elif self._anatomical_buffer.node_names != node_names:
            return

        if pose_scores is not None and np.asarray(pose_scores).shape[0] == n_nodes:
            score = np.asarray(pose_scores, dtype=np.float32).reshape(n_nodes)
        else:
            score = np.zeros(n_nodes, dtype=np.float32)

        if pose_node_valid is not None and np.asarray(pose_node_valid).shape[0] == n_nodes:
            valid = np.asarray(pose_node_valid, dtype=np.uint8).reshape(n_nodes)
        else:
            valid = np.isfinite(xy).all(axis=1).astype(np.uint8)

        self._anatomical_buffer.append_frame(
            frame_index,
            xy[:, 0],
            xy[:, 1],
            score,
            valid,
        )

    def _append_blob_frame(
        self,
        frame_index: int,
        blob_xy: Optional[np.ndarray],
        *,
        valid: bool,
        heading_rad: float,
        score: float,
    ) -> None:
        """Buffer one oriented blob polygon (full-image coordinates)."""
        if self._blob_buffer is None:
            return

        if blob_xy is None or not valid:
            self._blob_buffer.append_frame(
                frame_index,
                np.full((BLOB_VERTEX_COUNT, 2), np.nan, dtype=np.float32),
                valid=False,
                heading_rad=float("nan"),
                score=0.0,
            )
            return

        xy = np.asarray(blob_xy, dtype=np.float32)
        if xy.shape != (BLOB_VERTEX_COUNT, 2):
            return

        self._blob_buffer.append_frame(
            frame_index,
            xy,
            valid=True,
            heading_rad=float(heading_rad),
            score=float(score),
        )

    def start(self, frame_shape: tuple, fps: float = 30.0) -> Optional[Path]:
        """Start recording; return final video path. Writes to a temp file until stop() to avoid duplicate/partial-file issues (e.g. preview).
        Tries avc1 first (best for browser/Cursor preview); falls back to mp4v with no error if avc1 fails (e.g. OpenH264 missing). No extra installs.
        """
        self._fps = fps
        self._start_time = time.monotonic()
        if self.config.track_enable_backup:
            self._init_blob_capture()
        else:
            self._blob_buffer = None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        base = f"{self.animal_id}_{self.session_id}_{self.trial}"
        if self._virtual_source_video_path is not None:
            self._video_path = self._virtual_source_video_path
            self._video_path_temp = None
            self._video_writer = None
            return self._video_path
        if not HAS_CV2:
            return None
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
        region_code: str,
        valid: bool,
        duty_pct: float,
        spot_xy: Optional[Tuple[float, float]] = None,
        in_range_xy: Optional[Tuple[float, float]] = None,
        centroid_xy: Optional[Tuple[float, float]] = None,
        pose_xy: Optional[np.ndarray] = None,
        pose_scores: Optional[np.ndarray] = None,
        pose_node_valid: Optional[np.ndarray] = None,
        pose_node_names: Optional[Sequence[str]] = None,
        blob_xy: Optional[np.ndarray] = None,
        blob_valid: bool = False,
        blob_heading_rad: float = float("nan"),
        blob_score: float = 0.0,
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
                x=x_px,
                y=y_px,
                spot_x=float(spot_xy[0]) if spot_xy is not None else np.nan,
                spot_y=float(spot_xy[1]) if spot_xy is not None else np.nan,
                in_range_x=float(in_range_xy[0]) if in_range_xy is not None else np.nan,
                in_range_y=float(in_range_xy[1]) if in_range_xy is not None else np.nan,
                centroid_x=float(centroid_xy[0]) if centroid_xy is not None else np.nan,
                centroid_y=float(centroid_xy[1]) if centroid_xy is not None else np.nan,
                dist_to_exit_px=dist_to_exit_px,
                trial_state=trial_state,
                region_code=region_code,
                valid=valid,
            )
        )
        self._duty_w.append(duty_pct)
        self._duty_m.append(duty_pct)
        if pose_xy is not None and pose_node_names is not None:
            self._append_anatomical_pose(
                frame_index,
                pose_xy,
                pose_scores,
                pose_node_valid,
                pose_node_names,
            )
        if self._blob_buffer is not None:
            self._append_blob_frame(
                frame_index,
                blob_xy,
                valid=blob_valid,
                heading_rad=blob_heading_rad,
                score=blob_score,
            )

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
        self._anatomical_buffer = None
        self._blob_buffer = None

    def stop(
        self,
        exit_x_px: float,
        exit_y_px: float,
        timestamp_str: Optional[str] = None,
        on_video_path_conflict: Optional[Callable[[Path], VideoPathConflictChoice]] = None,
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
                    choice = (
                        conflict_choice
                        if conflict_choice is not None
                        else (
                            on_video_path_conflict(self._video_path)
                            if on_video_path_conflict is not None
                            else None
                        )
                    )
                elif conflict_choice is not None and conflict_choice not in (
                    "overwrite",
                    "discard",
                ):
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
                    new_path = (
                        self.output_dir / f"{self.animal_id}_{self.session_id}_{self.trial}.mp4"
                    )
                    self._video_path_temp.replace(new_path)
                    self._video_path = new_path
                else:
                    self._video_path_temp.replace(self._video_path)
        elif self._virtual_source_video_path is not None:
            self._video_path = self._virtual_source_video_path
        self._video_path_temp = None
        init_database(self.db_path, arena_type=self.config.arena_type)
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
                    experiment=animal_meta.experiment,
                    researcher=animal_meta.researcher,
                    drug=animal_meta.drug,
                    notes=animal_meta.notes,
                )
            g = ensure_trial_group(
                h5,
                self.animal_id,
                self.session_id,
                self.trial,
                video_path=video_path_for_storage(self._video_path) if self._video_path else None,
                sleap_path=None,
                run_phase=run_phase,
                run_mode=run_mode,
            )
            # trial_start_frame: absolute source frame index of first "run" row.
            # seek_to_frame: absolute frame where analysis window starts (virtual scrubber; 0 live).
            trial_start_frame_abs = 0
            for row in self._xy_rows:
                if (row.trial_state or "").strip().lower() == "run":
                    trial_start_frame_abs = int(row.frame_index)
                    break
            seek_to_frame = int(self._seek_to_frame)
            if self.config.arena_type == "radial_arm" and isinstance(
                self.config, RadialArmControllerConfig
            ):
                write_radial_arm_trial_settings(
                    g,
                    self.config,
                    timestamp=timestamp_str,
                    phase=run_phase,
                    run_mode=run_mode,
                    trial_start_frame=trial_start_frame_abs,
                    seek_to_frame=seek_to_frame,
                    ram_exit_arm_index=self._recording_ram_exit_arm_index,
                )
            else:
                arena = self.config.arena
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
                    exit_radius_px=arena.exit_radius_cm * arena.px_per_cm,
                    trial_start_frame=trial_start_frame_abs,
                    seek_to_frame=seek_to_frame,
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
                        arr[i]["region_code"] = encode_region_code_bytes(r.region_code)
                        arr[i]["is_moving"] = 1 if r.is_moving else 0

                    # Point-specific coordinates/validity
                    arr_spot[i]["x"] = r.spot_x
                    arr_spot[i]["y"] = r.spot_y
                    arr_spot[i]["valid"] = (
                        1 if (np.isfinite(r.spot_x) and np.isfinite(r.spot_y)) else 0
                    )

                    arr_in_range[i]["x"] = r.in_range_x
                    arr_in_range[i]["y"] = r.in_range_y
                    arr_in_range[i]["valid"] = (
                        1 if (np.isfinite(r.in_range_x) and np.isfinite(r.in_range_y)) else 0
                    )

                    arr_centroid[i]["x"] = r.centroid_x
                    arr_centroid[i]["y"] = r.centroid_y
                    arr_centroid[i]["valid"] = (
                        1 if (np.isfinite(r.centroid_x) and np.isfinite(r.centroid_y)) else 0
                    )

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
            if self._anatomical_buffer is not None:
                self._anatomical_buffer.flush(g, h5=h5)
            if self._blob_buffer is not None:
                self._blob_buffer.flush(g, h5=h5)
