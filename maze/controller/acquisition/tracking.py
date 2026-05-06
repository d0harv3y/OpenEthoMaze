"""
Real-time tracking: adaptive intensity threshold + morphology fallback (center-of-mass).

Optional SLEAP integration for primary; fallback when SLEAP unavailable or low confidence.
Streaming inference: single-frame SLEAP when a single-instance model path is provided.

This module also provides TrackingController for GUI orchestration (tracker cache,
async worker, run-every-N).

FPS note: When fallback finds in-range pixels, building a full-frame blob_mask (drawContours)
and drawing it in the GUI (blend overlay) can drop display FPS. Use show_blob_overlay=False
in FallbackTrackingConfig to skip blob mask build/draw and keep tracking position only.
"""

from __future__ import annotations

import logging
import math
import queue
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, List, Literal, Optional, Tuple, TYPE_CHECKING

import numpy as np

from . import app_logging
from .shared_config import AcquisitionConfig

_LOG = logging.getLogger("maze_acquisition")

if TYPE_CHECKING:
    import torch

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


SleapStatus = Literal["ok", "no_path", "not_single_instance", "load_failed"]


def scale_tracking_result_to_image_space(
    res: TrackingResult,
    inv_x: float,
    inv_y: float,
    full_hw: tuple[int, int],
) -> TrackingResult:
    """Map ``res`` from downscaled image coordinates back to full ``full_hw`` (H, W) space."""
    if inv_x == 1.0 and inv_y == 1.0:
        return res
    fh, fw = int(full_hw[0]), int(full_hw[1])
    nx = float(res.x_px) * inv_x
    ny = float(res.y_px) * inv_y
    pose = getattr(res, "pose_xy", None)
    pose_new = None
    if pose is not None and pose.size > 0 and pose.ndim == 2 and pose.shape[1] >= 2:
        pose_new = np.asarray(pose, dtype=np.float64).copy()
        pose_new[:, 0] *= inv_x
        pose_new[:, 1] *= inv_y
    in_r = getattr(res, "in_range_xy", None)
    in_new = None
    if in_r is not None and len(in_r) == 2:
        in_new = (float(in_r[0]) * inv_x, float(in_r[1]) * inv_y)
    blob = getattr(res, "blob_mask", None)
    blob_new = None
    if blob is not None and HAS_CV2 and blob.ndim == 2:
        if blob.shape[0] != fh or blob.shape[1] != fw:
            blob_new = cv2.resize(blob, (fw, fh), interpolation=cv2.INTER_NEAREST)
        else:
            blob_new = blob
    return replace(res, x_px=nx, y_px=ny, pose_xy=pose_new, in_range_xy=in_new, blob_mask=blob_new)


@dataclass
class TrackingResult:
    """Single-frame position and validity. Optional full pose for SLEAP overlay."""
    x_px: float
    y_px: float
    valid: bool
    source: str  # "sleap" or "fallback"
    confidence: float = 1.0
    # Full pose for skeleton overlay (SLEAP only); None for fallback
    pose_xy: Optional[np.ndarray] = None  # (nodes, 2) in image coords
    pose_scores: Optional[np.ndarray] = None  # (nodes,)
    pose_edge_inds: Optional[List[Tuple[int, int]]] = None  # (node_i, node_j) for drawing edges
    pose_node_names: Optional[List[str]] = None  # (nodes,) names for spot/fore-nodes; SLEAP only
    pose_node_valid: Optional[np.ndarray] = None  # (nodes,) bool: True where node score >= threshold; SLEAP only
    # Performance and fallback-reason indicators
    inference_time_s: float = 0.0  # time in SLEAP inference this frame; 0 for fallback
    sleap_confidence: Optional[float] = None  # raw SLEAP conf when fallback due to low conf
    # Binary mask (H, W) of the selected blob for overlay when fallback builds it; also attached
    # to SLEAP results when show_blob_overlay is enabled so the GUI can draw blob + skeleton.
    blob_mask: Optional[np.ndarray] = None
    # Independent fallback trajectory for "in-range" stream (when available).
    in_range_xy: Optional[Tuple[float, float]] = None


def _ensure_grayscale(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def _adaptive_threshold_com_impl(
    image: np.ndarray,
    morph_kernel_size: int = 5,
    min_area: int = 100,
    last_xy: Optional[Tuple[float, float]] = None,
    *,
    max_area: int = 0,
    max_jump_px: float = 0.0,
    selection_mode: str = "closest_else_largest",
    min_circularity: float = 0.0,
    range_low: int = 0,
    range_high: int = 255,
    return_blob_mask: bool = True,
    max_contours: int = 0,
) -> Tuple[float, float, bool, Optional[np.ndarray]]:
    """
    In-range intensity threshold + morphology + blob center-of-mass.

    Pipeline:
    1. Grayscale the image.
    2. Binarize with cv2.inRange: pixel on if range_low <= intensity <= range_high.
    3. Morphology: close (fill holes) then open (remove small noise) with ellipse kernel.
    4. Find contours; if max_contours > 0 keep only the largest max_contours by area.
       Then keep those with min_area <= area, (if max_area > 0) area <= max_area,
       and (if min_circularity > 0) circularity >= min_circularity (4*pi*area/perimeter^2).
    5. Pick blob by selection_mode (see doc).

    Returns (cx, cy, valid, blob_mask). blob_mask is (H,W) uint8, 255=blob, or None if no blob.
    """
    if not HAS_CV2:
        return (0.0, 0.0, False, None)
    gray = _ensure_grayscale(np.asarray(image, dtype=np.uint8))
    low = int(max(0, min(255, range_low)))
    high = int(max(0, min(255, range_high)))
    thresh = cv2.inRange(gray, low, high)
    k = morph_kernel_size
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Optionally cap contours to the largest N by area to bound worst-case cost
    if max_contours > 0 and len(contours) > max_contours:
        area_contour = [(cv2.contourArea(c), c) for c in contours]
        area_contour.sort(key=lambda x: x[0], reverse=True)
        contours = [c for _, c in area_contour[:max_contours]]
    candidates: List[Tuple[float, float, float, Any]] = []  # (cx, cy, area, contour)
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        if max_area > 0 and area > max_area:
            continue
        if min_circularity > 0:
            perim = cv2.arcLength(c, True)
            if perim <= 0:
                continue
            circ = 4.0 * math.pi * area / (perim * perim)
            if circ < min_circularity:
                continue
        M = cv2.moments(c)
        if M["m00"] > 0:
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]
            candidates.append((cx, cy, area, c))
    if not candidates:
        return (0.0, 0.0, False, None)
    # Selection by mode
    if selection_mode == "largest":
        best = max(candidates, key=lambda t: t[2])
        best_cx, best_cy, _, best_contour = best
    elif selection_mode == "closest" and last_xy is not None:
        lx, ly = last_xy
        best = min(candidates, key=lambda t: (t[0] - lx) ** 2 + (t[1] - ly) ** 2)
        best_cx, best_cy, _, best_contour = best
    elif selection_mode == "closest_else_largest" and last_xy is not None:
        lx, ly = last_xy
        best = min(candidates, key=lambda t: (t[0] - lx) ** 2 + (t[1] - ly) ** 2)
        best_cx, best_cy, _, best_contour = best
        if max_jump_px > 0:
            d = ((best_cx - lx) ** 2 + (best_cy - ly) ** 2) ** 0.5
            if d > max_jump_px:
                best = max(candidates, key=lambda t: t[2])
                best_cx, best_cy, _, best_contour = best
    else:
        best = max(candidates, key=lambda t: t[2])
        best_cx, best_cy, _, best_contour = best
    if not return_blob_mask:
        return (best_cx, best_cy, True, None)
    blob_mask = np.zeros(gray.shape, dtype=np.uint8)
    cv2.drawContours(blob_mask, [best_contour], -1, 255, -1)
    return (best_cx, best_cy, True, blob_mask)


def adaptive_threshold_com(
    image: np.ndarray,
    block_size: int = 15,
    morph_kernel_size: int = 5,
    min_area: int = 100,
) -> Tuple[float, float, bool]:
    """
    Public API used in tests: adaptive threshold center-of-mass.

    Args:
        image: Input image (H,W) or (H,W,C).
        block_size: Kept for backwards-compatibility with earlier API; mapped to
            morph_kernel_size when provided.
        morph_kernel_size: Morphology kernel size.
        min_area: Minimum blob area.

    Returns:
        (cx, cy, valid) where valid is False if no suitable blob is found.
    """
    k = morph_kernel_size if morph_kernel_size is not None else block_size
    cx, cy, valid, _ = _adaptive_threshold_com_impl(
        image,
        morph_kernel_size=k,
        min_area=min_area,
        last_xy=None,
        max_area=0,
        max_jump_px=0.0,
        selection_mode="closest_else_largest",
        min_circularity=0.0,
        # Use a limited intensity range so uniformly bright images produce no blob,
        # but darker-than-background blobs (rodent) are still detected.
        range_low=0,
        range_high=128,
        return_blob_mask=False,
        max_contours=0,
    )
    return cx, cy, valid


class AdaptiveThresholdTracker:
    """Fallback tracker: in-range threshold + morphology + CoM. Uses temporal consistency when available."""

    def __init__(
        self,
        morph_kernel_size: int = 5,
        min_area: int = 100,
        block_size: Optional[int] = None,
        max_area: int = 0,
        max_jump_px: float = 0.0,
        selection_mode: str = "closest_else_largest",
        min_circularity: float = 0.0,
        range_low: int = 0,
        range_high: int = 255,
        show_blob_overlay: bool = True,
        max_contours: int = 0,
    ):
        # block_size is a backwards-compatible alias for morph_kernel_size used in tests.
        self.morph_kernel_size = block_size if block_size is not None else morph_kernel_size
        self.min_area = min_area
        self.max_area = max_area
        self.max_jump_px = max_jump_px
        self.selection_mode = selection_mode
        self.min_circularity = min_circularity
        self.range_low = range_low
        self.range_high = range_high
        self._show_blob_overlay = show_blob_overlay
        self._max_contours = max_contours
        self._last_xy: Optional[Tuple[float, float]] = None

    def track(self, image: np.ndarray) -> TrackingResult:
        cx, cy, valid, blob_mask = _adaptive_threshold_com_impl(
            image,
            morph_kernel_size=self.morph_kernel_size,
            min_area=self.min_area,
            last_xy=self._last_xy,
            max_area=self.max_area,
            max_jump_px=self.max_jump_px,
            selection_mode=self.selection_mode,
            min_circularity=self.min_circularity,
            range_low=self.range_low,
            range_high=self.range_high,
            return_blob_mask=self._show_blob_overlay,
            max_contours=self._max_contours,
        )
        if valid:
            self._last_xy = (cx, cy)
        _LOG.debug(
            "fallback track: cx=%.1f cy=%.1f valid=%s",
            cx, cy, valid,
        )
        return TrackingResult(
            x_px=cx,
            y_px=cy,
            valid=valid,
            source="fallback",
            confidence=0.9 if valid else 0.0,
            blob_mask=blob_mask,
            in_range_xy=(float(cx), float(cy)) if valid else None,
        )


def _numpy_to_tensor_batch(img: np.ndarray) -> "torch.Tensor":
    """Convert numpy image (H, W) or (H, W, C) to torch (1, C, H, W) float."""
    import torch
    arr = np.asarray(img, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]  # (1, H, W)
    else:
        arr = np.transpose(arr, (2, 0, 1))  # (C, H, W)
        arr = arr[np.newaxis, :, :, :]  # (1, C, H, W)
    t = torch.from_numpy(arr)
    if t.dim() == 3:
        t = t.unsqueeze(0)  # (1, 1, H, W)
    return t


class HybridTracker:
    """
    Primary: SLEAP (if available and confident); fallback: adaptive threshold CoM.
    Streaming inference supported for single-instance SLEAP-NN models only.
    """

    def __init__(
        self,
        sleap_model_paths: Optional[list] = None,
        confidence_threshold: float = 0.5,
        fallback_tracker: Optional[AdaptiveThresholdTracker] = None,
        min_nodes_required: int = 1,
        *,
        run_fallback: bool = True,
    ):
        self.sleap_model_paths = sleap_model_paths or []
        self.confidence_threshold = confidence_threshold
        self.min_nodes_required = max(1, min_nodes_required)
        self._run_fallback = bool(run_fallback)
        self._fallback = fallback_tracker or AdaptiveThresholdTracker()
        self._sleap_predictor = None  # lazy init; SingleInstancePredictor or None
        self._sleap_status: SleapStatus = "no_path"
        self._sleap_status_error: Optional[str] = None
        self._sleap_device: Optional[str] = None  # "cuda:0" or "cpu" after successful load
        self._sleap_lock = threading.Lock()
        self._sleap_last_attempt_s: float = 0.0
        self._sleap_last_fail_s: Optional[float] = None
        # Prevent tight retry loops (and import races) when SLEAP load fails.
        self._sleap_fail_cooldown_s: float = 2.0
        # Log the first load failure once (UI polls status every frame).
        self._sleap_load_failure_logged: bool = False

    def get_sleap_status(self) -> Tuple[SleapStatus, Optional[str]]:
        """Return (status, error_message). status: ok | no_path | not_single_instance | load_failed.
        Calls _ensure_sleap() so status is current when path is set."""
        self._ensure_sleap()
        return (self._sleap_status, self._sleap_status_error)

    def _ensure_sleap(self) -> bool:
        if not self.sleap_model_paths:
            self._sleap_status = "no_path"
            self._sleap_status_error = None
            self._sleap_device = None
            return False
        if self._sleap_predictor is not None:
            self._sleap_status = "ok"
            self._sleap_status_error = None
            return True

        # If we recently failed, avoid hammering imports repeatedly.
        now_s = time.monotonic()
        if (
            self._sleap_last_fail_s is not None
            and (now_s - self._sleap_last_fail_s) < self._sleap_fail_cooldown_s
        ):
            return False

        with self._sleap_lock:
            # Re-check after waiting for the lock.
            if self._sleap_predictor is not None:
                self._sleap_status = "ok"
                self._sleap_status_error = None
                return True
            # Another thread may have tried recently while we waited.
            now_s = time.monotonic()
            if (
                self._sleap_last_fail_s is not None
                and (now_s - self._sleap_last_fail_s) < self._sleap_fail_cooldown_s
            ):
                return False

            self._sleap_last_attempt_s = now_s
            try:
                # Force a clean re-import if a previous attempt left a partially
                # initialized module in sys.modules.
                import sys

                sys.modules.pop("sleap_nn.inference.predictors", None)

                # We only support streaming with single-instance models here.
                # Importing the Predictor base class can fail if the module
                # partially loads, so we avoid it.
                from sleap_nn.inference.predictors import SingleInstancePredictor

                path = Path(self.sleap_model_paths[0])
                if not path.is_dir():
                    self._sleap_status = "load_failed"
                    self._sleap_status_error = "Path is not a directory"
                    return False

                import torch

                if torch.cuda.is_available():
                    device = "cuda:0"  # explicit first GPU for inference
                    try:
                        device_name = torch.cuda.get_device_name(0)
                        _LOG.info(
                            "SLEAP: using CUDA device 0 (%s)", device_name
                        )
                    except Exception:
                        _LOG.info("SLEAP: using CUDA device 0")
                else:
                    device = "cpu"
                    _LOG.warning(
                        "SLEAP: CUDA not available, using CPU (inference will be slower). "
                        "Install PyTorch with CUDA (e.g. pip install torch --index-url https://download.pytorch.org/whl/cu121) to use GPU."
                    )

                # sleap-nn in this environment errors on preprocess_config=None, so
                # explicitly pass the model's preprocessing block from training_config.
                # This preserves inference-time parity (resize/channels) with GUI runs.
                from omegaconf import OmegaConf

                preprocess_cfg = OmegaConf.create({})
                train_cfg_path = path / "training_config.yaml"
                if train_cfg_path.exists():
                    try:
                        train_cfg = OmegaConf.load(str(train_cfg_path))
                        pre = (
                            train_cfg.get("data_config", {})
                            .get("preprocessing", {})
                        )
                        preprocess_cfg = OmegaConf.create(pre)
                    except Exception:
                        _LOG.warning(
                            "SLEAP: failed to load preprocessing from %s; "
                            "falling back to empty preprocess config",
                            train_cfg_path,
                            exc_info=True,
                        )

                predictor = SingleInstancePredictor.from_trained_models(
                    confmap_ckpt_path=str(path),
                    device=device,
                    batch_size=1,
                    preprocess_config=preprocess_cfg,
                )

                self._sleap_predictor = predictor
                actual = next(predictor.confmap_model.parameters()).device
                self._sleap_device = str(actual)
                _LOG.info("SLEAP: model loaded on %s", actual)
                self._sleap_status = "ok"
                self._sleap_status_error = None
                self._sleap_load_failure_logged = False
                return True
            except Exception as e:
                self._sleap_status = "load_failed"
                import traceback

                self._sleap_last_fail_s = time.monotonic()
                # Include traceback so Help -> View error log has the real origin.
                self._sleap_status_error = (
                    f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                )
                if not self._sleap_load_failure_logged:
                    self._sleap_load_failure_logged = True
                    app_logging.log_error(
                        "SLEAP: model load failed (subsequent failures are not re-logged):\n"
                        + (self._sleap_status_error or str(e))
                    )
                return False

    def _get_skeleton_node_names(self) -> List[str]:
        """Get node names from predictor skeleton (for spot/fore-nodes overlay)."""
        if self._sleap_predictor is None:
            return []
        try:
            skel = self._sleap_predictor.skeletons[0]
            names = getattr(skel, "node_names", None)
            return list(names) if names is not None else []
        except (IndexError, TypeError, AttributeError):
            return []

    def _get_skeleton_edge_inds(self) -> List[Tuple[int, int]]:
        """Get (node_i, node_j) edge list from predictor skeleton for overlay."""
        if self._sleap_predictor is None:
            return []
        try:
            skel = self._sleap_predictor.skeletons[0]
        except (IndexError, TypeError, AttributeError):
            return []
        edge_inds = getattr(skel, "edge_inds", None)
        if edge_inds is not None:
            arr = np.asarray(edge_inds)
            if arr.ndim == 2 and arr.shape[1] >= 2:
                return [(int(arr[i, 0]), int(arr[i, 1])) for i in range(len(arr))]
        edges = getattr(skel, "edges", None)
        if edges is not None:
            name_to_idx = {
                name: i for i, name in enumerate(getattr(skel, "node_names", []))
            }
            out = []
            for e in edges:
                a, b = e[0], e[1]
                if isinstance(a, (int, np.integer)) and isinstance(b, (int, np.integer)):
                    out.append((int(a), int(b)))
                elif a in name_to_idx and b in name_to_idx:
                    out.append((name_to_idx[a], name_to_idx[b]))
            return out
        return []

    def _predict_frame_sleap(
        self, image: np.ndarray
    ) -> Optional[Tuple[float, float, float, np.ndarray, np.ndarray, float]]:
        """Run SLEAP on one frame. Returns (x_px, y_px, confidence, pose_xy, pose_scores, inference_time_s) or None."""
        if self._sleap_predictor is None:
            return None
        try:
            import torch
            from sleap_nn.data.resizing import (
                apply_pad_to_stride,
                apply_sizematcher,
                resize_image,
            )
            import torchvision.transforms.v2.functional as tvf
            pred = self._sleap_predictor
            cfg = pred.preprocess_config or {}
            device = next(pred.confmap_model.parameters()).device
            # Enforce grayscale input for ORM controller inference.
            image_sleap = image
            if HAS_CV2 and image_sleap.ndim == 3:
                image_sleap = cv2.cvtColor(
                    np.asarray(image_sleap, dtype=np.uint8), cv2.COLOR_BGR2GRAY
                )
            # (1, C, H, W)
            def ensure_4d(t: "torch.Tensor") -> "torch.Tensor":
                if t.dim() == 3:
                    return t.unsqueeze(0)
                return t

            img = _numpy_to_tensor_batch(image_sleap).to(device)
            if cfg.get("ensure_rgb") and img.shape[1] != 3:
                img = img.repeat(1, 3, 1, 1)
            elif cfg.get("ensure_grayscale") and img.shape[1] != 1:
                img = tvf.rgb_to_grayscale(img, num_output_channels=1)
            img, eff_scale = apply_sizematcher(
                img,
                cfg.get("max_height"),
                cfg.get("max_width"),
            )
            img = ensure_4d(img)
            scale = cfg.get("scale") if cfg.get("scale") is not None else 1.0
            if scale != 1.0:
                img = resize_image(img, scale)
                img = ensure_4d(img)
            img = apply_pad_to_stride(img, pred.max_stride)
            img = ensure_4d(img)
            eff_scale_t = torch.tensor([eff_scale], dtype=torch.float32, device=device)
            # SingleInstanceConfmapsLightningModule.forward() expects (batch, n_samples, C, H, W) and squeezes dim=1
            if img.dim() == 4:
                img = img.unsqueeze(1)  # (B, C, H, W) -> (B, 1, C, H, W)
            t0 = time.perf_counter()
            _LOG.debug("SLEAP inference img.shape before inference_model: %s", tuple(img.shape))
            with torch.inference_mode():
                out_list = pred.inference_model({"image": img, "eff_scale": eff_scale_t})
            inference_time_s = time.perf_counter() - t0
            if not out_list:
                _LOG.debug("SLEAP: out_list empty")
                return None
            out = out_list[0]
            peaks = out["pred_instance_peaks"]  # (1, nodes, 2)
            vals = out["pred_peak_values"]      # (1, nodes)
            peaks = peaks.cpu().numpy()
            vals = vals.cpu().numpy()
            if peaks.size == 0 or vals.size == 0:
                _LOG.debug("SLEAP: peaks or vals empty (peaks.size=%s vals.size=%s)", peaks.size, vals.size)
                return None
            # Valid keypoints: above model threshold
            thresh = pred.peak_threshold if hasattr(pred, "peak_threshold") else 0.2
            valid = vals[0] >= thresh
            if not np.any(valid):
                max_val = float(np.max(vals[0])) if vals.size else 0
                _LOG.debug(
                    "SLEAP: no keypoints above threshold %.2f (max score=%.3f)",
                    thresh, max_val,
                )
                return None
            pts = peaks[0][valid]
            scores = vals[0][valid]
            cx = float(np.mean(pts[:, 0]))
            cy = float(np.mean(pts[:, 1]))
            conf = float(np.mean(scores))
            # Full pose for overlay: all nodes (use peaks[0], vals[0])
            pose_xy = np.asarray(peaks[0], dtype=np.float64)
            pose_scores = np.asarray(vals[0], dtype=np.float64)
            return (cx, cy, conf, pose_xy, pose_scores, inference_time_s)
        except Exception as e:
            _LOG.debug("SLEAP: _predict_frame_sleap exception: %s", e, exc_info=True)
            return None

    def track(
        self,
        image: np.ndarray,
        *,
        sleap_image: Optional[np.ndarray] = None,
    ) -> TrackingResult:
        if not self._run_fallback:
            # In SLEAP-only mode, always prefer the explicit SLEAP frame when provided.
            return self._track_sleap_only(image, sleap_image=sleap_image)

        # Always compute fallback so "in-range" can be recorded continuously.
        fallback_res = self._fallback.track(image)
        if self._ensure_sleap() and self._sleap_predictor is not None:
            sleap_input = image if sleap_image is None else sleap_image
            res = self._predict_frame_sleap(sleap_input)
            if res is not None:
                x, y, conf, pose_xy, pose_scores, inference_time_s = res
                # Per-node validity: keep nodes above threshold, reject others
                pose_node_valid = np.asarray(
                    pose_scores >= self.confidence_threshold, dtype=bool
                )
                n_valid = int(np.sum(pose_node_valid))
                if n_valid < self.min_nodes_required:
                    # Too few nodes above threshold: fall back to backup tracker
                    min_score = float(np.min(pose_scores)) if pose_scores.size else 0.0
                    _LOG.debug(
                        "SLEAP: %d nodes above threshold (need %d), min=%.3f; using fallback",
                        n_valid, self.min_nodes_required, min_score,
                    )
                    fallback_res.sleap_confidence = conf
                    fallback_res.inference_time_s = inference_time_s
                    return fallback_res
                # Use SLEAP: track position = centroid of valid nodes only; invalid nodes still in pose for overlay
                pts_valid = pose_xy[pose_node_valid]
                x = float(np.mean(pts_valid[:, 0]))
                y = float(np.mean(pts_valid[:, 1]))
                conf_valid = float(np.mean(pose_scores[pose_node_valid]))
                edge_inds = self._get_skeleton_edge_inds()
                return TrackingResult(
                    x_px=x,
                    y_px=y,
                    valid=True,
                    source="sleap",
                    confidence=conf_valid,
                    pose_xy=pose_xy,
                    pose_scores=pose_scores,
                    pose_edge_inds=edge_inds,
                    pose_node_names=self._get_skeleton_node_names(),
                    pose_node_valid=pose_node_valid,
                    inference_time_s=inference_time_s,
                    in_range_xy=fallback_res.in_range_xy,
                    blob_mask=fallback_res.blob_mask,
                )
            _LOG.debug("SLEAP: _predict_frame_sleap returned None, using fallback")
        else:
            _LOG.debug("SLEAP: not available (_ensure_sleap=False or no predictor), using fallback")
        return fallback_res

    def _track_sleap_only(
        self,
        image: np.ndarray,
        *,
        sleap_image: Optional[np.ndarray] = None,
    ) -> TrackingResult:
        """SLEAP inference only: no adaptive-threshold fallback or in-range stream."""
        if not (self._ensure_sleap() and self._sleap_predictor is not None):
            return TrackingResult(0.0, 0.0, False, "sleap", confidence=0.0)
        sleap_input = image if sleap_image is None else sleap_image
        res = self._predict_frame_sleap(sleap_input)
        if res is None:
            return TrackingResult(0.0, 0.0, False, "sleap", confidence=0.0)
        _x, _y, conf, pose_xy, pose_scores, inference_time_s = res
        pose_node_valid = np.asarray(pose_scores >= self.confidence_threshold, dtype=bool)
        n_valid = int(np.sum(pose_node_valid))
        if n_valid < self.min_nodes_required:
            return TrackingResult(
                0.0,
                0.0,
                False,
                "sleap",
                confidence=0.0,
                pose_xy=pose_xy,
                pose_scores=pose_scores,
                pose_edge_inds=self._get_skeleton_edge_inds(),
                pose_node_names=self._get_skeleton_node_names(),
                pose_node_valid=pose_node_valid,
                inference_time_s=inference_time_s,
                sleap_confidence=float(conf),
            )
        pts_valid = pose_xy[pose_node_valid]
        x = float(np.mean(pts_valid[:, 0]))
        y = float(np.mean(pts_valid[:, 1]))
        conf_valid = float(np.mean(pose_scores[pose_node_valid]))
        edge_inds = self._get_skeleton_edge_inds()
        return TrackingResult(
            x_px=x,
            y_px=y,
            valid=True,
            source="sleap",
            confidence=conf_valid,
            pose_xy=pose_xy,
            pose_scores=pose_scores,
            pose_edge_inds=edge_inds,
            pose_node_names=self._get_skeleton_node_names(),
            pose_node_valid=pose_node_valid,
            inference_time_s=inference_time_s,
            in_range_xy=None,
            blob_mask=None,
        )


# -----------------------------------------------------------------------------
# TrackingController: GUI orchestration (tracker cache, async worker, run-every-N)
# -----------------------------------------------------------------------------

_TRACKING_STALE_S = 0.132  # ~2× 33 ms; matches GUI constant


def _build_or_refresh_tracker(
    config: AcquisitionConfig,
    cached_key: Optional[tuple],
    cached_tracker: Optional[object],
    *,
    sleap_path: str,
    enable_backup: bool,
    enable_sleap: bool,
) -> Tuple[object, tuple]:
    """
    Build or refresh the tracker used for real-time tracking.

    Parameters
    ----------
    sleap_path:
        Path to the SLEAP model directory (may be ignored when ``enable_sleap`` is False).
    enable_backup:
        When True, adaptive-threshold fallback runs (alone or under Hybrid).
    enable_sleap:
        When True and path is set, SLEAP runs (alone or under Hybrid).
    """
    raw_path = (sleap_path or "").strip()
    eff_path = raw_path if enable_sleap else ""
    eb = bool(enable_backup)
    es = bool(enable_sleap)
    if not eb and not eff_path:
        eb = True

    use_hybrid = bool(eff_path and HybridTracker is not None)
    run_fb = eb if use_hybrid else True

    confidence_pct = float(config.sleap_confidence_pct) / 100.0
    ft = config.fallback_tracking
    min_sleap_nodes = 1

    if ft is not None:
        min_area = ft.min_area
        max_area = ft.max_area
        morph_kernel = ft.morph_kernel_size | 1
        max_jump_px = ft.max_jump_px
        selection_mode = ft.selection_mode
        min_circularity = ft.min_circularity
        range_low = ft.range_low
        range_high = ft.range_high
        min_sleap_nodes = ft.min_sleap_nodes
        max_contours = ft.max_contours
    else:
        min_area, max_area, morph_kernel = 80, 0, 5
        max_jump_px = 0.0
        selection_mode = "closest_else_largest"
        min_circularity = 0.0
        range_low, range_high = 0, 255
        max_contours = 0

    show_blob_overlay = ft.show_blob_overlay if ft is not None else True
    key = (
        eff_path,
        eb,
        es,
        run_fb,
        confidence_pct,
        min_sleap_nodes,
        min_area,
        max_area,
        morph_kernel,
        max_jump_px,
        selection_mode,
        min_circularity,
        range_low,
        range_high,
        show_blob_overlay,
        max_contours,
    )

    if key == cached_key and cached_tracker is not None:
        return cached_tracker, key
    fallback = AdaptiveThresholdTracker(
        min_area=min_area,
        morph_kernel_size=morph_kernel,
        max_area=max_area,
        max_jump_px=max_jump_px,
        selection_mode=selection_mode,
        min_circularity=min_circularity,
        range_low=range_low,
        range_high=range_high,
        show_blob_overlay=show_blob_overlay,
        max_contours=max_contours,
    )

    if use_hybrid:
        tracker = HybridTracker(
            sleap_model_paths=[eff_path],
            confidence_threshold=confidence_pct,
            fallback_tracker=fallback,
            min_nodes_required=min_sleap_nodes,
            run_fallback=run_fb,
        )
    else:
        tracker = fallback

    return tracker, key


def build_tracker_for_batch_encode(
    config: AcquisitionConfig,
    *,
    model_dir: str,
) -> object:
    """
    Fresh tracker for offline video passes (pipeline inference materialization).

    Uses the same hybrid/fallback construction as the live GUI; ``model_dir`` overrides
    ``config.sleap_model_path`` for this encode only.
    """
    tracker, _ = _build_or_refresh_tracker(
        config,
        None,
        None,
        sleap_path=str(model_dir or "").strip(),
        enable_backup=bool(getattr(config, "track_enable_backup", True)),
        enable_sleap=bool(str(model_dir or "").strip()),
    )
    return tracker


def _tracking_worker_loop(
    q: queue.Queue,
    lock: threading.Lock,
    result_holder: list,
    result_time_holder: list,
    running_holder: list,
) -> None:
    """
    Background thread: dequeue ``(frame, sleap_frame, tracker, inv_x, inv_y, fh, fw)``, run ``track``,
    map coordinates back to full crop space when ``inv`` differs from 1.
    """
    while running_holder[0]:
        try:
            item = q.get(timeout=0.05)
        except queue.Empty:
            continue
        if item is None:
            break
        frame, sleap_frame, tracker, inv_x, inv_y, fh, fw = item
        if frame is None or tracker is None:
            continue
        try:
            if sleap_frame is None:
                res = tracker.track(frame)
            else:
                try:
                    res = tracker.track(frame, sleap_image=sleap_frame)
                except TypeError:
                    # Fallback-only trackers don't accept a separate SLEAP image.
                    res = tracker.track(frame)
            if res is not None:
                res = scale_tracking_result_to_image_space(
                    res, float(inv_x), float(inv_y), (int(fh), int(fw))
                )
        except Exception as e:  # pragma: no cover - defensive logging
            app_logging.log_error(f"tracking worker: track() failed: {e}")
            res = None
        with lock:
            result_holder[0] = res
            result_time_holder[0] = time.monotonic()
    result_holder[0] = None
    result_time_holder[0] = 0.0


class TrackingController:
    """
    Orchestrates real-time tracking for the GUI.

    Responsibilities (implemented across refactor steps):
    - Own a cached tracker (HybridTracker + AdaptiveThresholdTracker) based on `AcquisitionConfig`
      and the current SLEAP model path / backup-only settings.
    - Optionally run tracking in an async worker thread and queue when async is enabled.
    - Implement run-every-N SLEAP logic using `config.sleap_every_n`.
    - Expose a small API that `MainWindow` can use from camera callbacks.
    """

    def __init__(self, config: AcquisitionConfig) -> None:
        """
        Initialize a new `TrackingController`.

        Parameters
        ----------
        config:
            The controller configuration object. A reference is kept and may be
            updated via `set_config` when settings or profiles change.
        """
        self._config = config

        # Tracker cache
        self._cached_tracker: Optional[object] = None
        self._cached_tracker_key: Optional[tuple] = None
        self._track_frame_counter: int = 0
        self._last_tracking_result: Optional[TrackingResult] = None

        # Async tracking state
        self._async_enabled: bool = False
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._result_holder: list = [None]  # [TrackingResult | None]
        self._result_time_holder: list = [0.0]
        self._running_holder: list = [False]
        self._worker_thread: Optional[threading.Thread] = None
        self._queue_full_log_last_s: float = 0.0
        self._no_result_log_last_s: float = 0.0

        # GUI-owned parameters (mirrors config; compared each frame for no-op updates).
        self._sleap_path: str = ""
        self._enable_backup: bool = True
        self._enable_sleap: bool = True

    # Internal helpers -----------------------------------------------------------

    def _ensure_tracker(self) -> object:
        """Build or refresh the cached tracker and return it."""
        tracker, key = _build_or_refresh_tracker(
            self._config,
            self._cached_tracker_key,
            self._cached_tracker,
            sleap_path=self._sleap_path,
            enable_backup=self._enable_backup,
            enable_sleap=self._enable_sleap,
        )
        if key != self._cached_tracker_key:
            # Cache changed: reset frame counter and last result so run-every-N
            # logic restarts cleanly.
            self._cached_tracker_key = key
            self._cached_tracker = tracker
            self._track_frame_counter = 0
            self._last_tracking_result = None
        return tracker

    # Public API -----------------------------------------------------------------

    def start(self, async_enabled: bool) -> None:
        """
        Start tracking.

        This prepares internal state for either synchronous or asynchronous
        tracking. When `async_enabled` is True, a worker thread and queue are
        created and started; otherwise, tracking is performed synchronously in
        `submit_frame`.

        The detailed implementation of async orchestration is added in later
        refactor steps; for now this method only records the desired mode and
        ensures any existing worker is stopped.
        """
        self._async_enabled = async_enabled

        # Stop any existing worker and clear results.
        self.stop()

        if not self._async_enabled:
            return

        # Fresh async state.
        self._queue = queue.Queue(maxsize=1)
        self._result_holder = [None]
        self._result_time_holder = [0.0]
        self._running_holder = [True]
        self._queue_full_log_last_s = 0.0
        self._no_result_log_last_s = 0.0

        self._worker_thread = threading.Thread(
            target=_tracking_worker_loop,
            args=(
                self._queue,
                self._lock,
                self._result_holder,
                self._result_time_holder,
                self._running_holder,
            ),
            daemon=True,
        )
        self._worker_thread.start()

    def stop(self) -> None:
        """
        Stop tracking and shut down any worker thread.

        This method is safe to call multiple times. It will signal the worker
        thread (if any) to exit, join it with a small timeout, and clear the
        latest result holders.
        """
        self._running_holder[0] = False
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=1.0)
            self._worker_thread = None
        with self._lock:
            self._result_holder[0] = None
            self._result_time_holder[0] = 0.0

    def set_tracker_sources(self, sleap_path: str, enable_backup: bool, enable_sleap: bool) -> None:
        """
        Update SLEAP path and backup/SLEAP enable flags. Must no-op when unchanged
        (per-frame calls from the GUI) to avoid reloading SLEAP every tick.
        """
        path = sleap_path.strip()
        eb = bool(enable_backup)
        es = bool(enable_sleap)
        if path == self._sleap_path and eb == self._enable_backup and es == self._enable_sleap:
            return
        self._sleap_path = path
        self._enable_backup = eb
        self._enable_sleap = es
        self._cached_tracker_key = None
        self._last_tracking_result = None
        self._track_frame_counter = 0

    def set_config(self, config: AcquisitionConfig) -> None:
        """
        Replace the current `AcquisitionConfig` and invalidate cached trackers.

        This should be called after settings or profile changes so that the
        next frame submission rebuilds the tracker with updated parameters.
        """
        self._config = config
        self._cached_tracker_key = None
        self._last_tracking_result = None
        self._track_frame_counter = 0

    def submit_frame(
        self,
        image: np.ndarray,
        now_s: float,
        *,
        sleap_image: Optional[np.ndarray] = None,
    ) -> None:
        """
        Submit a frame for tracking.

        Parameters
        ----------
        image:
            Frame for fallback tracking (may be masked/cropped).
        sleap_image:
            Optional full raw frame for SLEAP inference. When provided, SLEAP
            runs on this frame while fallback still uses ``image``.
        now_s:
            Timestamp (e.g. `time.monotonic()`) corresponding to this frame.

        In async mode, this enqueues the frame for the worker thread.
        In sync mode, this performs tracking immediately (respecting
        `config.sleap_every_n`) and stores the resulting `TrackingResult`.
        """
        tracker = self._ensure_tracker()
        img_arr = np.asarray(image, dtype=np.uint8)
        sleap_arr = (
            np.asarray(sleap_image, dtype=np.uint8)
            if sleap_image is not None
            else None
        )
        inv_x, inv_y = 1.0, 1.0
        small = img_arr
        fh, fw = int(img_arr.shape[0]), int(img_arr.shape[1])

        if self._async_enabled:
            queue_was_full = False
            try:
                # Worker owns the copy so the caller can safely reuse its array.
                self._queue.put_nowait(
                    (
                        small.copy(),
                        (sleap_arr.copy() if sleap_arr is not None else None),
                        tracker,
                        inv_x,
                        inv_y,
                        fh,
                        fw,
                    )
                )
            except queue.Full:
                queue_was_full = True
                if now_s - self._queue_full_log_last_s >= 1.0:
                    self._queue_full_log_last_s = now_s
                    app_logging.log_debug(
                        "async tracking: queue full, frame dropped (worker slower than camera)"
                    )

            # Optionally log when the worker appears stuck: no result yet and
            # queue is full every frame for an extended period.
            if queue_was_full:
                with self._lock:
                    res = self._result_holder[0]
                if res is None and now_s - self._no_result_log_last_s >= 10.0:
                    self._no_result_log_last_s = now_s
                    app_logging.log_error(
                        "Async tracking: no result from worker yet (queue full every frame). "
                        "Worker may be stuck in SLEAP inference. Try: disable async tracking or wait longer."
                    )
            return

        # Synchronous path with run-every-N SLEAP logic.
        run_every_n = max(1, int(self._config.sleap_every_n))
        do_track = (
            run_every_n <= 1
            or self._last_tracking_result is None
            or (self._track_frame_counter % run_every_n == 0)
        )
        if do_track:
            if sleap_arr is None:
                res = tracker.track(small)
            else:
                try:
                    res = tracker.track(small, sleap_image=sleap_arr)
                except TypeError:
                    res = tracker.track(small)
            if res is not None:
                res = scale_tracking_result_to_image_space(res, inv_x, inv_y, (fh, fw))
            self._last_tracking_result = res
        else:
            res = self._last_tracking_result

        self._track_frame_counter += 1

        with self._lock:
            self._result_holder[0] = res
            self._result_time_holder[0] = now_s

    def get_overlay_state(self, now_s: Optional[float] = None) -> dict[str, Any]:
        """
        Convenience method: return a dict of fields used by the GUI overlay.

        The dict is intended to contain:
        - `track_xy`: Optional[Tuple[float, float]]
        - `track_valid`: bool
        - `track_source`: str
        - `pose_xy`, `pose_scores`, `pose_edge_inds`, `pose_node_names`,
          `pose_node_valid`, `blob_mask`
        - `source_label`, `conf_label`, `inference_label`, `stale_label`

        The exact contents and semantics are wired up in later refactor steps
        when `MainWindow` is migrated to use `TrackingController`.
        """
        if now_s is None:
            now_s = time.monotonic()

        with self._lock:
            res = self._result_holder[0]
            result_time = self._result_time_holder[0]

        if res is None:
            stale_label = "—"
            if self._async_enabled and result_time > 0 and (now_s - result_time) > _TRACKING_STALE_S:
                stale_label = "catching up"
            return {
                "track_xy": None,
                "track_valid": False,
                "track_source": "fallback",
                "pose_xy": None,
                "pose_scores": None,
                "pose_edge_inds": None,
                "pose_node_names": None,
                "pose_node_valid": None,
                "blob_mask": None,
                "in_range_xy": None,
                "source_label": "—",
                "conf_label": "—",
                "inference_label": "—",
                "stale_label": stale_label,
            }

        track_xy = (res.x_px, res.y_px)
        track_valid = bool(res.valid)
        track_source = res.source or "fallback"
        inf_ms = getattr(res, "inference_time_s", 0.0) * 1000.0
        if track_source == "sleap":
            conf_label = f"{res.confidence * 100:.0f}%"
        elif getattr(res, "sleap_confidence", None) is not None:
            conf_label = f"SLEAP {res.sleap_confidence * 100:.0f}%"
        else:
            conf_label = "—"
        inference_label = f"{inf_ms:.0f} ms" if inf_ms > 0 else "—"

        stale_label = "—"
        if self._async_enabled and result_time > 0 and (now_s - result_time) > _TRACKING_STALE_S:
            stale_label = "catching up"

        return {
            "track_xy": track_xy,
            "track_valid": track_valid,
            "track_source": track_source,
            "pose_xy": getattr(res, "pose_xy", None),
            "pose_scores": getattr(res, "pose_scores", None),
            "pose_edge_inds": getattr(res, "pose_edge_inds", None),
            "pose_node_names": getattr(res, "pose_node_names", None),
            "pose_node_valid": getattr(res, "pose_node_valid", None),
            "blob_mask": getattr(res, "blob_mask", None),
            "in_range_xy": getattr(res, "in_range_xy", None),
            "source_label": track_source,
            "conf_label": conf_label,
            "inference_label": inference_label,
            "stale_label": stale_label,
        }

    def get_sleap_status_label(self) -> tuple[str, str]:
        """
        Return (label_text, tooltip) for the SLEAP status indicator.

        This inspects the underlying HybridTracker when available.
        """
        sleap_path = self._sleap_path
        tracker = self._cached_tracker
        if not sleap_path or HybridTracker is None or not isinstance(tracker, HybridTracker):
            return "—", "SLEAP model load status"

        status, err = tracker.get_sleap_status()
        if status == "ok":
            dev = getattr(tracker, "_sleap_device", None)
            tip = f"SLEAP model on {dev}" if dev else "SLEAP model load status"
            # Extra detail when torch is CPU-only: helps diagnose why SLEAP
            # never selects CUDA even if a GPU is present.
            if dev == "cpu":
                try:
                    import torch  # local import: torch may be optional until SLEAP extra installed

                    tip = (
                        f"SLEAP model on cpu "
                        f"(torch={torch.__version__}, "
                        f"cuda_available={torch.cuda.is_available()}, "
                        f"torch.version.cuda={getattr(torch.version, 'cuda', None)})"
                    )
                except Exception:
                    pass
            return "ready", tip
        if status == "no_path":
            return "No path", "SLEAP model load status"
        if status == "not_single_instance":
            return "Not single-instance", "SLEAP model load status"
        err_str = (str(err).strip() if err is not None else "") or "Unknown error"
        return "failed", "SLEAP model load status. Error: " + err_str
