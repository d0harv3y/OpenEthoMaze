"""
Verify SLEAP model node order and draw labeled nodes on a sample frame.

Discovers .avi/.slp pairs via file discovery, picks a random trial with both,
finds a frame where all nodes are visible, and draws node labels on that frame
(one-off QC-style image). Also prints file node order vs STANDARD_NODE_NAMES.

Usage:
    uv run python scripts/verify_sleap_nodes.py [--output path] [--data-dir path]

Output:
    - Printed node comparison (file order vs config)
    - Image with labeled nodes saved to --output (default: verify_sleap_nodes.png)
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import cv2
except ImportError:
    print("OpenCV (cv2) is required. Install with: uv pip install opencv-python")
    sys.exit(1)

from vast_pipeline.config import DATA_DIR, STANDARD_NODE_NAMES
from vast_pipeline.io.file_discovery import discover_trials
from vast_pipeline.io.sleap_loader import load_sleap_file


def _trials_with_video_and_sleap(result):
    """Yield trials that have both video_path and sleap_path."""
    for t in result.trials:
        if t.video_path is not None and t.sleap_path is not None and t.video_path.exists() and t.sleap_path.exists():
            yield t


def _find_frame_all_nodes_visible(trace_data) -> int | None:
    """Return first frame index where every node has valid (finite) x,y; else None."""
    n_frames = trace_data.n_frames
    node_names = trace_data.node_names
    if not node_names or n_frames == 0:
        return None
    for fi in range(n_frames):
        all_ok = True
        for name in node_names:
            if name not in trace_data.traces:
                all_ok = False
                break
            x = trace_data.traces[name]["x"]
            y = trace_data.traces[name]["y"]
            if fi >= len(x) or not (np.isfinite(x[fi]) and np.isfinite(y[fi])):
                all_ok = False
                break
        if all_ok:
            return fi
    return None


def _read_frame(video_path: Path, frame_index: int) -> np.ndarray | None:
    """Read a single frame (BGR) from video; None on failure."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


def _draw_labeled_nodes(
    frame: np.ndarray,
    trace_data,
    frame_index: int,
    radius: int = 1,
    font_scale: float = 0.3,
    thickness: int = 1,
) -> np.ndarray:
    """Draw circles and labels for each node on frame. Returns BGR image."""
    out = frame.copy()
    n_nodes = len(trace_data.node_names)
    # BGR palette: green, blue, red, yellow, magenta, cyan, orange, lime
    palette = [
        (0, 255, 0), (255, 0, 0), (0, 0, 255), (0, 255, 255),
        (255, 0, 255), (255, 255, 0), (0, 165, 255), (0, 255, 128),
    ]
    colors = [palette[i % len(palette)] for i in range(n_nodes)]

    for i, name in enumerate(trace_data.node_names):
        if name not in trace_data.traces:
            continue
        xarr = trace_data.traces[name]["x"]
        yarr = trace_data.traces[name]["y"]
        if frame_index >= len(xarr):
            continue
        x, y = float(xarr[frame_index]), float(yarr[frame_index])
        if not (np.isfinite(x) and np.isfinite(y)):
            continue
        ix, iy = int(round(x)), int(round(y))
        color = colors[i]
        cv2.circle(out, (ix, iy), radius, color, 2)
        label = f"{i}:{name}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        # Label above point, avoid clipping
        tx = max(0, min(ix - tw // 2, out.shape[1] - tw))
        ty = max(th + 2, iy - radius - 2)
        cv2.putText(out, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SLEAP nodes and draw labeled frame.")
    parser.add_argument("--output", "-o", type=Path, default=Path("verify_sleap_nodes.png"), help="Output image path")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="Data directory for discovery")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for choosing trial")
    args = parser.parse_args()

    result = discover_trials(args.data_dir)
    candidates = list(_trials_with_video_and_sleap(result))
    if not candidates:
        print("No trials with both .avi and .slp found. Check DATA_DIR and that discovery includes SLEAP files.")
        sys.exit(1)

    if args.seed is not None:
        random.seed(args.seed)
    trial = random.choice(candidates)
    video_path = trial.video_path
    sleap_path = trial.sleap_path
    print(f"Using trial: {trial.trial_key}")
    print(f"  Video: {video_path}")
    print(f"  SLEAP: {sleap_path}")

    trace_data = load_sleap_file(sleap_path)
    if trace_data is None:
        print("Failed to load SLEAP file.")
        sys.exit(1)

    file_nodes = trace_data.node_names
    print("\nNode names in file (order):")
    for i, name in enumerate(file_nodes):
        print(f"  {i}: {name}")
    print("\nSTANDARD_NODE_NAMES (config):")
    for i, name in enumerate(STANDARD_NODE_NAMES):
        print(f"  {i}: {name}")
    if list(file_nodes) == list(STANDARD_NODE_NAMES):
        print("\nMatch: file order matches STANDARD_NODE_NAMES.")
    else:
        print("\nMismatch: update config or model so node order agrees.")

    frame_index = _find_frame_all_nodes_visible(trace_data)
    if frame_index is None:
        frame_index = max(0, (trace_data.n_frames - 1) // 2)
        print(f"\nNo frame with all nodes visible; using frame {frame_index}.")
    else:
        print(f"\nUsing frame {frame_index} (all nodes visible).")

    frame = _read_frame(video_path, frame_index)
    if frame is None:
        print("Failed to read video frame.")
        sys.exit(1)

    out_img = _draw_labeled_nodes(frame, trace_data, frame_index)
    out_path = args.output
    if not out_path.is_absolute():
        out_path = Path(__file__).resolve().parent.parent / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), out_img)
    print(f"\nSaved labeled frame to {out_path}")


if __name__ == "__main__":
    main()
