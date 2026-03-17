"""
Input H5 file loader for VAST pipeline.

Parses the source HDF5 files containing trial settings and legacy tracking data.

H5 Structure:
    <animal_id>/<session>/<trial>/
        data: structured array with fields:
            timer0, timer1, subtrial, iti, X, Y, Correct, Incorrect, R, G, B, W, M
        settings: dataset with attributes:
            ROI: "X=187,Y=149,R=147,pxcm=2.422145"
            color: "Green/low/dim"
            stage: "VAST"
            timestamp: "9/25/2023 5:35:42 PM"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import h5py
import numpy as np

from ..config import DEFAULT_PX_PER_CM


@dataclass
class TrialSettings:
    """Container for trial settings parsed from input H5 file."""

    # Arena geometry from ROI string (X,Y = arena center, R = radius)
    arena_center_x_px: float
    arena_center_y_px: float
    arena_radius_px: float
    px_per_cm: float

    # Trial metadata
    stage: str
    color: str
    timestamp: Optional[datetime]

    # Exit position from settings array (row 1)
    exit_number: Optional[int] = None  # From settings[1, 7]
    exit_x: Optional[float] = None  # From settings[1, 1] - actual exit X coord
    exit_y: Optional[float] = None  # From settings[1, 2] - actual exit Y coord

    # Original ROI string for debugging/verification
    roi_old: Optional[str] = None

    @property
    def exit_pos(self) -> Optional[tuple[float, float]]:
        """Exit position as tuple, or None if not available."""
        if self.exit_x is not None and self.exit_y is not None:
            return (self.exit_x, self.exit_y)
        return None

    @property
    def arena_radius_cm(self) -> float:
        """Arena radius in cm."""
        return self.arena_radius_px / self.px_per_cm

    @property
    def cm_per_px(self) -> float:
        """Inverse of px_per_cm for convenience."""
        return 1.0 / self.px_per_cm if self.px_per_cm > 0 else 0.0


@dataclass
class TrialData:
    """Container for trial tracking data from input H5 file."""
    
    # Time arrays
    timer0: np.ndarray  # Primary timer
    timer1: np.ndarray  # Secondary timer
    
    # Trial structure
    subtrial: np.ndarray
    iti: np.ndarray  # Inter-trial interval flag
    
    # Legacy tracking (before SLEAP)
    x: np.ndarray
    y: np.ndarray
    
    # Performance
    correct: np.ndarray
    incorrect: np.ndarray
    
    # Motor outputs (vibration intensity)
    r: np.ndarray  # Red motor
    g: np.ndarray  # Green motor
    b: np.ndarray  # Blue motor
    w: np.ndarray  # White motor
    m: np.ndarray  # Master/main motor
    
    @property
    def n_frames(self) -> int:
        """Number of frames in the trial."""
        return len(self.timer0)

    @property
    def duration_s(self) -> float:
        """Trial duration in seconds (from timer)."""
        if len(self.timer0) > 0:
            return float(self.timer0[-1] - self.timer0[0])
        return 0.0

    @property
    def fps(self) -> float:
        """FPS computed from timer0 intervals (more accurate than video metadata)."""
        if len(self.timer0) > 1:
            duration = float(self.timer0[-1] - self.timer0[0])
            if duration > 0:
                return (len(self.timer0) - 1) / duration
        return 0.0

    @property
    def trial_start_frame(self) -> int:
        """
        First frame index where subtrial == 1 (trial begins after ITI).
        If subtrial never equals 1, returns 0 (analyze full recording).
        """
        idx = np.flatnonzero(self.subtrial.astype(np.int64) == 1)
        return int(idx[0]) if len(idx) > 0 else 0


def parse_roi_string(roi_str: str) -> dict[str, float]:
    """
    Parse ROI attribute string into components.
    
    Args:
        roi_str: String like "X=187,Y=149,R=147,pxcm=2.422145"
        
    Returns:
        Dictionary with keys: x, y, r, pxcm
    """
    result = {}
    
    # Parse each key=value pair
    for match in re.finditer(r"(\w+)=([\d.]+)", roi_str):
        key = match.group(1).lower()
        value = float(match.group(2))
        result[key] = value
    
    return result


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    Parse timestamp string from H5 settings.
    
    Args:
        timestamp_str: String like "9/25/2023 5:35:42 PM"
        
    Returns:
        datetime object or None if parsing fails
    """
    formats = [
        "%m/%d/%Y %I:%M:%S %p",  # 9/25/2023 5:35:42 PM
        "%m/%d/%Y %H:%M:%S",      # 9/25/2023 17:35:42
        "%Y-%m-%d %H:%M:%S",      # 2023-09-25 17:35:42
        "%Y-%m-%dT%H:%M:%S",      # 2023-09-25T17:35:42
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str.strip(), fmt)
        except ValueError:
            continue
    
    return None


def load_trial_settings(
    h5_path: Path,
    animal_id: str,
    session: str,
    trial: str
) -> TrialSettings:
    """
    Load trial settings from an input H5 file.

    Args:
        h5_path: Path to input H5 file
        animal_id: Animal ID (top-level group)
        session: Session key (e.g., "S01")
        trial: Trial key (e.g., "T01")

    Returns:
        TrialSettings object with parsed ROI and metadata

    Raises:
        KeyError: If trial path doesn't exist in H5 file
        ValueError: If required attributes are missing
    """
    with h5py.File(h5_path, "r") as f:
        trial_path = f"{animal_id}/{session}/{trial}"

        if trial_path not in f:
            raise KeyError(f"Trial path not found in H5: {trial_path}")

        trial_group = f[trial_path]

        # Get settings dataset
        if "settings" not in trial_group:
            raise ValueError(f"No 'settings' dataset in trial: {trial_path}")

        settings_ds = trial_group["settings"]

        # Parse ROI attribute
        roi_str = settings_ds.attrs.get("ROI", "")
        if isinstance(roi_str, bytes):
            roi_str = roi_str.decode("utf-8")

        roi = parse_roi_string(roi_str)

        # Extract arena geometry from ROI string (X,Y = arena center, R = radius)
        arena_center_x_px = roi.get("x", 0.0)
        arena_center_y_px = roi.get("y", 0.0)
        arena_radius_px = roi.get("r", 0.0)
        px_per_cm = roi.get("pxcm", DEFAULT_PX_PER_CM)

        # Parse other attributes
        stage = settings_ds.attrs.get("stage", "VAST")
        if isinstance(stage, bytes):
            stage = stage.decode("utf-8")

        color = settings_ds.attrs.get("color", "")
        if isinstance(color, bytes):
            color = color.decode("utf-8")

        timestamp_str = settings_ds.attrs.get("timestamp", "")
        if isinstance(timestamp_str, bytes):
            timestamp_str = timestamp_str.decode("utf-8")
        timestamp = parse_timestamp(timestamp_str)

        # Read settings dataset array for exit position
        # The settings dataset contains a 2D array. Row 1 (index 1) has:
        #   Index 1: exit_x coordinate
        #   Index 2: exit_y coordinate
        #   Index 7: exit_number
        exit_number = None
        exit_x = None
        exit_y = None

        try:
            settings_arr = settings_ds[:]
            if settings_arr.ndim >= 2 and settings_arr.shape[0] >= 2:
                row = settings_arr[1]  # Second row (index 1)
                if len(row) > 7:
                    exit_number = int(row[7])
                if len(row) > 2:
                    exit_x = float(row[2])
                    exit_y = float(row[1])
            elif settings_arr.ndim == 1 and len(settings_arr) > 7:
                # Fallback: 1D array case
                exit_x = float(settings_arr[2]) if len(settings_arr) > 1 else None
                exit_y = float(settings_arr[1]) if len(settings_arr) > 2 else None
                exit_number = int(settings_arr[7]) if len(settings_arr) > 7 else None
        except (IndexError, ValueError, TypeError):
            # If extraction fails, leave as None
            pass

        return TrialSettings(
            arena_center_x_px=arena_center_x_px,
            arena_center_y_px=arena_center_y_px,
            arena_radius_px=arena_radius_px,
            px_per_cm=px_per_cm,
            stage=stage,
            color=color,
            timestamp=timestamp,
            exit_number=exit_number,
            exit_x=exit_x,
            exit_y=exit_y,
            roi_old=roi_str if roi_str else None,
        )


def load_trial_data(
    h5_path: Path,
    animal_id: str,
    session: str,
    trial: str
) -> TrialData:
    """
    Load trial tracking data from an input H5 file.
    
    Args:
        h5_path: Path to input H5 file
        animal_id: Animal ID (top-level group)
        session: Session key (e.g., "S01")
        trial: Trial key (e.g., "T01")
        
    Returns:
        TrialData object with tracking arrays
        
    Raises:
        KeyError: If trial path doesn't exist in H5 file
        ValueError: If required data is missing
    """
    with h5py.File(h5_path, "r") as f:
        trial_path = f"{animal_id}/{session}/{trial}"
        
        if trial_path not in f:
            raise KeyError(f"Trial path not found in H5: {trial_path}")
        
        trial_group = f[trial_path]
        
        # Get data dataset
        if "data" not in trial_group:
            raise ValueError(f"No 'data' dataset in trial: {trial_path}")
        
        data = trial_group["data"][:]
        
        # Extract fields from structured array (H5 columns X,Y -> TrialData.x = horizontal, .y = vertical)
        # print("hi")
        return TrialData(
            timer0=data["timer0"].astype(np.float64),
            timer1=data["timer1"].astype(np.float64),
            subtrial=data["subtrial"].astype(np.float64),
            iti=data["iti"].astype(np.float64),
            x=data["Y"].astype(np.float64),
            y=data["X"].astype(np.float64),
            correct=data["Correct"].astype(np.float64),
            incorrect=data["Incorrect"].astype(np.float64),
            r=data["R"].astype(np.float64),
            g=data["G"].astype(np.float64),
            b=data["B"].astype(np.float64),
            w=data["W"].astype(np.float64),
            m=data["M"].astype(np.float64),
        )


def load_trial(
    h5_path: Path,
    animal_id: str,
    session: str,
    trial: str
) -> tuple[TrialSettings, TrialData]:
    """
    Load both settings and data for a trial.
    
    Args:
        h5_path: Path to input H5 file
        animal_id: Animal ID
        session: Session key
        trial: Trial key
        
    Returns:
        Tuple of (TrialSettings, TrialData)
    """
    settings = load_trial_settings(h5_path, animal_id, session, trial)
    data = load_trial_data(h5_path, animal_id, session, trial)
    return settings, data


def get_trial_list(h5_path: Path) -> list[tuple[str, str, str]]:
    """
    Get list of all trials in an H5 file.
    
    Args:
        h5_path: Path to input H5 file
        
    Returns:
        List of (animal_id, session, trial) tuples
    """
    trials = []
    
    with h5py.File(h5_path, "r") as f:
        for animal_id in f.keys():
            animal_group = f[animal_id]
            if not isinstance(animal_group, h5py.Group):
                continue
            
            for session in animal_group.keys():
                session_group = animal_group[session]
                if not isinstance(session_group, h5py.Group):
                    continue
                
                for trial in session_group.keys():
                    trial_group = session_group[trial]
                    if isinstance(trial_group, h5py.Group):
                        if "data" in trial_group or "settings" in trial_group:
                            trials.append((animal_id, session, trial))
    
    return sorted(trials)


if __name__ == "__main__":
    # Test loading
    from ..config import DATA_DIR
    
    test_h5 = DATA_DIR / "Kevan Lim" / "VASTcontKL_AZ_male_S1-10.hdf5"
    
    if test_h5.exists():
        trials = get_trial_list(test_h5)
        print(f"Found {len(trials)} trials")
        
        if trials:
            animal_id, session, trial = trials[0]
            settings, data = load_trial(test_h5, animal_id, session, trial)
            
            print(f"\nTrial: {animal_id}/{session}/{trial}")
            print(f"  Exit: ({settings.exit_x_px:.1f}, {settings.exit_y_px:.1f}) px")
            print(f"  Arena radius: {settings.arena_radius_px:.1f} px ({settings.arena_radius_cm:.1f} cm)")
            print(f"  px/cm: {settings.px_per_cm:.3f}")
            print(f"  Stage: {settings.stage}")
            print(f"  Timestamp: {settings.timestamp}")
            print(f"  Data frames: {data.n_frames}")
            print(f"  Duration: {data.duration_s:.1f} s")
