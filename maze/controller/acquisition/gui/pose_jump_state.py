from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class PoseJumpState:
    """Debounce large per-node SLEAP jumps across consecutive frames."""

    last_pose_xy: Optional[np.ndarray] = None
    node_jump_streak: Optional[np.ndarray] = None

    def reset(self) -> None:
        self.last_pose_xy = None
        self.node_jump_streak = None

    def update(
        self,
        pose_xy: Optional[np.ndarray],
        node_max_jump_px: float,
        node_jump_confirm_frames: int,
    ) -> Optional[np.ndarray]:
        """Return per-node validity after filtering teleports against prior accepted pose."""
        if pose_xy is None or pose_xy.shape[0] == 0:
            return None
        n = pose_xy.shape[0]
        finite = np.isfinite(pose_xy).all(axis=1)
        confirm_n = max(1, int(node_jump_confirm_frames))
        if node_max_jump_px <= 0:
            self.last_pose_xy = np.asarray(pose_xy, dtype=np.float64)
            self.node_jump_streak = None
            return finite
        if self.last_pose_xy is None or self.last_pose_xy.shape[0] != n:
            self.last_pose_xy = np.asarray(pose_xy, dtype=np.float64)
            self.node_jump_streak = np.zeros(n, dtype=np.int32)
            return finite
        if self.node_jump_streak is None or self.node_jump_streak.shape[0] != n:
            self.node_jump_streak = np.zeros(n, dtype=np.int32)
        node_valid = finite.copy()
        max_sq = float(node_max_jump_px) * float(node_max_jump_px)
        force_reset = False
        for i in range(n):
            if not finite[i]:
                node_valid[i] = False
                self.node_jump_streak[i] = 0
                continue
            dx = float(pose_xy[i, 0]) - float(self.last_pose_xy[i, 0])
            dy = float(pose_xy[i, 1]) - float(self.last_pose_xy[i, 1])
            if dx * dx + dy * dy <= max_sq:
                self.last_pose_xy[i, 0] = float(pose_xy[i, 0])
                self.last_pose_xy[i, 1] = float(pose_xy[i, 1])
                self.node_jump_streak[i] = 0
            else:
                self.node_jump_streak[i] += 1
                if self.node_jump_streak[i] >= confirm_n:
                    force_reset = True
                    break
                node_valid[i] = False
        if force_reset:
            self.last_pose_xy = np.asarray(pose_xy, dtype=np.float64)
            self.node_jump_streak = np.zeros(n, dtype=np.int32)
            return finite
        return node_valid
