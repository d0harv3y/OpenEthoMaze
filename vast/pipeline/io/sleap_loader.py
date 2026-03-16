"""
SLEAP tracking data loader for VAST pipeline.

Handles loading SLEAP prediction files (.h5.slp, .slp, .analysis.h5)
and extracting keypoint traces.

Note: This module is ready for use once SLEAP model training is complete
and predictions are available.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..storage.h5_db import TrialKey

import h5py
import numpy as np

from ..config import (
    FALLBACK_NODE_INDEX,
    IN_RANGE_POINT_NAME,
    SKELETON_EDGES,
    STANDARD_NODE_NAMES,
    SPOT_NODE_NAMES,
)


def get_skeleton_edges() -> list[tuple[int, int]]:
    """
    Return skeleton edge list as node index pairs for STANDARD_NODE_NAMES.
    Uses the fixed SKELETON_EDGES (node name pairs) from config; each edge
    is converted to (index_a, index_b). Skips any pair with an unknown node name.
    """
    name_to_idx = {name: i for i, name in enumerate(STANDARD_NODE_NAMES)}
    out: list[tuple[int, int]] = []
    for (na, nb) in SKELETON_EDGES:
        if na in name_to_idx and nb in name_to_idx:
            out.append((name_to_idx[na], name_to_idx[nb]))
    return out


@dataclass
class TraceData:
    """Container for SLEAP trace data for a single trial."""
    
    # Per-node tracking data: {node_name: {'x': array, 'y': array, 'score': array, 'visible': array}}
    traces: dict[str, dict[str, np.ndarray]] = field(default_factory=dict)
    
    # Ordered list of node names
    node_names: list[str] = field(default_factory=list)
    
    # Number of frames
    n_frames: int = 0
    
    # Original file path
    source_path: Optional[Path] = None
    
    # FPS (may be extracted from file or set externally)
    fps: float = 30.0
    
    def get_node_xy(self, node_name: str) -> Optional[np.ndarray]:
        """
        Get XY coordinates for a node.
        
        Returns:
            Array of shape (n_frames, 2) or None if node not found
        """
        if node_name not in self.traces:
            return None
        node = self.traces[node_name]
        return np.column_stack([node['x'], node['y']])
    
    def get_centroid(self) -> np.ndarray:
        """
        Compute centroid (mean of all nodes) for each frame.
        
        Returns:
            Array of shape (n_frames, 2)
        """
        x_all = []
        y_all = []
        
        for node_name in self.node_names:
            if node_name in self.traces:
                x_all.append(self.traces[node_name]['x'])
                y_all.append(self.traces[node_name]['y'])
        
        if not x_all:
            return np.full((self.n_frames, 2), np.nan)
        
        x_stack = np.column_stack(x_all)
        y_stack = np.column_stack(y_all)
        
        return np.column_stack([
            np.nanmean(x_stack, axis=1),
            np.nanmean(y_stack, axis=1)
        ])
    
    def get_spot(self, spot_nodes: tuple[str, ...] = SPOT_NODE_NAMES) -> np.ndarray:
        """
        Compute "spot" position (mean of selected front-body nodes).
        
        Args:
            spot_nodes: Tuple of node names to average
            
        Returns:
            Array of shape (n_frames, 2)
        """
        x_all = []
        y_all = []
        
        for node_name in spot_nodes:
            if node_name in self.traces:
                x_all.append(self.traces[node_name]['x'])
                y_all.append(self.traces[node_name]['y'])
        
        if not x_all:
            # Fall back to centroid
            return self.get_centroid()
        
        x_stack = np.column_stack(x_all)
        y_stack = np.column_stack(y_all)
        
        return np.column_stack([
            np.nanmean(x_stack, axis=1),
            np.nanmean(y_stack, axis=1)
        ])
    
    def get_confidence_mask(self, threshold: float = 0.2) -> np.ndarray:
        """
        Get per-frame mask where enough nodes have sufficient confidence.
        
        Args:
            threshold: Minimum confidence score
            
        Returns:
            Boolean array of shape (n_frames,)
        """
        confident_counts = np.zeros(self.n_frames)
        
        for node_name in self.node_names:
            if node_name in self.traces:
                scores = self.traces[node_name].get('score', np.ones(self.n_frames))
                confident_counts += (scores >= threshold)
        
        return confident_counts >= 3  # At least 3 confident nodes


def load_slp_file(slp_path: Path) -> Optional[TraceData]:
    """
    Load SLEAP .h5.slp or .slp file.
    
    The .h5.slp format contains:
    - metadata: JSON with node names
    - pred_points: Predicted keypoint coordinates
    - instances: Instance groupings
    - frames: Frame-level indexing
    
    Args:
        slp_path: Path to SLEAP file
        
    Returns:
        TraceData object or None if loading fails
    """
    if not slp_path.exists():
        print(f"SLEAP file not found: {slp_path}")
        return None
    
    try:
        with h5py.File(slp_path, "r") as f:
            # Get node names from metadata
            meta_json = f["metadata"].attrs["json"]
            if isinstance(meta_json, bytes):
                meta_json = meta_json.decode("utf-8")
            meta = json.loads(meta_json)
            original_node_labels = [n["name"] for n in meta["nodes"]]
            
            # Get raw data
            pred_points = f["pred_points"][:]
            instances = f["instances"][:]
            frames = f["frames"][:]
            
            n_frames = len(frames)
            n_nodes = len(original_node_labels)
            
            # Initialize trace arrays
            traces = {}
            for node_name in STANDARD_NODE_NAMES:
                traces[node_name] = {
                    'x': np.full(n_frames, np.nan, dtype=np.float32),
                    'y': np.full(n_frames, np.nan, dtype=np.float32),
                    'score': np.zeros(n_frames, dtype=np.float32),
                    'visible': np.zeros(n_frames, dtype=bool),
                }
            
            # Process each frame
            for frame_idx, frame_data in enumerate(frames):
                instance_start = frame_data['instance_id_start']
                instance_end = frame_data['instance_id_end']
                
                if instance_start >= instance_end:
                    continue
                
                # Get first instance for this frame
                instance_data = instances[instance_start]
                point_start = instance_data['point_id_start']
                point_end = instance_data['point_id_end']
                
                if point_start >= point_end:
                    continue
                
                instance_points = pred_points[point_start:point_end]
                
                # Map points to standard node order using fixed indices
                for point_idx, point_data in enumerate(instance_points):
                    if point_idx >= n_nodes:
                        break
                    
                    # Use fixed index mapping (ignore SLEAP metadata names)
                    if point_idx < len(STANDARD_NODE_NAMES):
                        node_name = STANDARD_NODE_NAMES[point_idx]
                    else:
                        continue
                    
                    x = point_data['x']
                    y = point_data['y']
                    score = point_data.get('score', 1.0) if hasattr(point_data, 'get') else (
                        point_data['score'] if 'score' in point_data.dtype.names else 1.0
                    )
                    
                    visible = not (np.isnan(x) or np.isnan(y))
                    
                    traces[node_name]['x'][frame_idx] = x
                    traces[node_name]['y'][frame_idx] = y
                    traces[node_name]['score'][frame_idx] = score
                    traces[node_name]['visible'][frame_idx] = visible
            
            return TraceData(
                traces=traces,
                node_names=STANDARD_NODE_NAMES.copy(),
                n_frames=n_frames,
                source_path=slp_path,
            )
    
    except Exception as e:
        print(f"Failed to load SLEAP file {slp_path}: {e}")
        return None


def load_analysis_h5(h5_path: Path) -> Optional[TraceData]:
    """
    Load SLEAP .analysis.h5 export file.
    
    The analysis.h5 format contains:
    - tracks: Shape (T, 2, N, F) - tracks, xy, nodes, frames
    - point_scores: Confidence scores
    - node_names: Node name list
    - track_occupancy: Which frames have valid tracks
    
    Args:
        h5_path: Path to analysis H5 file
        
    Returns:
        TraceData object or None if loading fails
    """
    if not h5_path.exists():
        print(f"SLEAP analysis file not found: {h5_path}")
        return None
    
    try:
        with h5py.File(h5_path, "r") as f:
            tracks = f["tracks"][:]  # (T, 2, N, F) or similar
            
            # Handle different array shapes
            if tracks.ndim == 4:
                # (tracks, xy, nodes, frames) -> use first track
                n_frames = tracks.shape[3]
                n_nodes = tracks.shape[2]
                x_all = tracks[0, 0, :, :]  # (nodes, frames)
                y_all = tracks[0, 1, :, :]
            else:
                print(f"Unexpected tracks shape: {tracks.shape}")
                return None
            
            # Get scores if available
            if "point_scores" in f:
                scores_all = f["point_scores"][:]
                if scores_all.ndim == 3:
                    scores_all = scores_all[0]  # (nodes, frames)
            else:
                scores_all = np.ones((n_nodes, n_frames))
            
            # Initialize traces with standard node names
            traces = {}
            for i, node_name in enumerate(STANDARD_NODE_NAMES):
                if i < n_nodes:
                    x = x_all[i, :]
                    y = y_all[i, :]
                    scores = scores_all[i, :] if i < scores_all.shape[0] else np.ones(n_frames)
                    visible = ~(np.isnan(x) | np.isnan(y))
                else:
                    x = np.full(n_frames, np.nan)
                    y = np.full(n_frames, np.nan)
                    scores = np.zeros(n_frames)
                    visible = np.zeros(n_frames, dtype=bool)
                
                traces[node_name] = {
                    'x': x.astype(np.float32),
                    'y': y.astype(np.float32),
                    'score': scores.astype(np.float32),
                    'visible': visible,
                }
            
            return TraceData(
                traces=traces,
                node_names=STANDARD_NODE_NAMES.copy(),
                n_frames=n_frames,
                source_path=h5_path,
            )
    
    except Exception as e:
        print(f"Failed to load SLEAP analysis file {h5_path}: {e}")
        return None


def load_sleap_file(sleap_path: Path) -> Optional[TraceData]:
    """
    Load SLEAP tracking data from any supported format.

    Automatically detects file type and uses appropriate loader.

    Args:
        sleap_path: Path to SLEAP file (.slp, .h5.slp, or .analysis.h5)

    Returns:
        TraceData object or None if loading fails
    """
    sleap_path = Path(sleap_path)

    if not sleap_path.exists():
        print(f"SLEAP file not found: {sleap_path}")
        return None

    name = sleap_path.name.lower()

    if name.endswith(".analysis.h5"):
        return load_analysis_h5(sleap_path)
    elif name.endswith(".h5.slp") or name.endswith(".slp"):
        return load_slp_file(sleap_path)
    else:
        # Try both formats
        result = load_slp_file(sleap_path)
        if result is None:
            result = load_analysis_h5(sleap_path)
        return result


def trace_data_from_realtime_xy(
    db_path: Optional[Path],
    key: "TrialKey",
    point_name: str = "spot",
    fps: float = 30.0,
) -> Optional[TraceData]:
    """
    Build TraceData from controller-written real-time XY table in the output H5.

    Used when no SLEAP file is available; VAST can still compute ambulation and
    exit metrics from the real-time tracking written by the circular open-field
    controller (Option B).

    Args:
        db_path: Path to output HDF5 database
        key: Trial key (animal_id, session, trial)
        point_name: Tracking point name (e.g. "spot")
        fps: FPS for the trial (from trial attrs or default)

    Returns:
        TraceData with a single node (point_name), or None if xy table missing
    """
    from ..storage.h5_db import read_xy_table

    xy_table = read_xy_table(db_path, key, point_name)
    if xy_table is None or len(xy_table) == 0:
        return None

    x = np.asarray(xy_table["x"], dtype=np.float64)
    y = np.asarray(xy_table["y"], dtype=np.float64)
    n = len(x)
    if "valid" in xy_table.dtype.names:
        valid = np.asarray(xy_table["valid"], dtype=np.float64)
    else:
        valid = np.ones(n, dtype=np.float64)
    score = np.where(
        (np.isfinite(x) & np.isfinite(y)),
        valid,
        0.0,
    ).astype(np.float64)
    visible = (score > 0.5).astype(np.float64)

    traces = {
        point_name: {
            "x": x,
            "y": y,
            "score": score,
            "visible": visible,
        }
    }
    return TraceData(
        traces=traces,
        node_names=[point_name],
        n_frames=n,
        fps=fps,
        source_path=None,
    )


def trace_data_from_legacy_xy(
    h5_path: Path,
    animal_id: str,
    session: str,
    trial: str,
    fps: float = 30.0,
) -> Optional[TraceData]:
    """
    Build TraceData from legacy input H5 data array (X, Y columns).

    Skips the first row (legacy software inits with an all-zeros row).
    All remaining frames are treated as valid. Used when output DB has no
    ambulation_metrics/in-range/xy (e.g. legacy ingest).

    Args:
        h5_path: Path to input H5 file
        animal_id, session, trial: Trial location in H5
        fps: FPS for the trial (from settings or default)

    Returns:
        TraceData with single node IN_RANGE_POINT_NAME, or None if no data
    """
    from ..io.input_h5_loader import load_trial_data

    try:
        data = load_trial_data(h5_path, animal_id, session, trial)
    except (KeyError, ValueError):
        return None
    x = np.asarray(data.x, dtype=np.float64)
    y = np.asarray(data.y, dtype=np.float64)
    n = len(x)
    if n <= 1:
        return None
    # Skip first row (legacy all-zeros init)
    x = x[1:]
    y = y[1:]
    n = len(x)
    valid = np.ones(n, dtype=np.float64)
    score = np.where(
        (np.isfinite(x) & np.isfinite(y)),
        valid,
        0.0,
    ).astype(np.float64)
    visible = (score > 0.5).astype(np.float64)
    traces = {
        IN_RANGE_POINT_NAME: {
            "x": x,
            "y": y,
            "score": score,
            "visible": visible,
        }
    }
    return TraceData(
        traces=traces,
        node_names=[IN_RANGE_POINT_NAME],
        n_frames=n,
        fps=fps,
        source_path=h5_path,
    )


def apply_jump_filter(
    trace: TraceData,
    max_jump_cm: float = 15.0,
    px_per_cm: float = 2.42,
    lookahead_frames: int = 3,
) -> TraceData:
    """
    Filter out tracking jumps that exceed physical plausibility.
    
    Large jumps (>max_jump_cm per frame) are set to NaN unless
    confirmed by consistent position in subsequent frames.
    
    Args:
        trace: Input TraceData
        max_jump_cm: Maximum allowed jump in cm
        px_per_cm: Calibration factor
        lookahead_frames: Frames to check for confirmation
        
    Returns:
        Filtered TraceData (modified in place)
    """
    max_jump_px = max_jump_cm * px_per_cm
    
    for node_name in trace.node_names:
        if node_name not in trace.traces:
            continue
        
        x = trace.traces[node_name]['x'].copy()
        y = trace.traces[node_name]['y'].copy()
        
        for i in range(1, len(x)):
            if np.isnan(x[i]) or np.isnan(x[i-1]):
                continue
            
            dx = x[i] - x[i-1]
            dy = y[i] - y[i-1]
            jump = np.sqrt(dx*dx + dy*dy)
            
            if jump > max_jump_px:
                # Check if jump is confirmed by subsequent frames
                confirmed = False
                for j in range(1, lookahead_frames + 1):
                    if i + j >= len(x):
                        break
                    if np.isnan(x[i+j]):
                        continue
                    # If subsequent frame is close to jumped position, it's real
                    dist = np.sqrt((x[i+j] - x[i])**2 + (y[i+j] - y[i])**2)
                    if dist < max_jump_px:
                        confirmed = True
                        break
                
                if not confirmed:
                    x[i] = np.nan
                    y[i] = np.nan
        
        trace.traces[node_name]['x'] = x
        trace.traces[node_name]['y'] = y
        trace.traces[node_name]['visible'] = ~(np.isnan(x) | np.isnan(y))
    
    return trace
