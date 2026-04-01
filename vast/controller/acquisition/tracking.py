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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Literal, Optional, Tuple, TYPE_CHECKING

import numpy as np

from . import app_logging
from .config import ControllerConfig

_LOG = logging.getLogger("vast_controller")

if TYPE_CHECKING:
    import torch

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


SleapStatus = Literal["ok", "no_path", "not_single_instance", "load_failed"]


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
    # Fallback only: binary mask (H, W) of the selected blob for overlay; None otherwise
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
        best_cx, best_cy, best_area, best_contour = best
    elif selection_mode == "closest" and last_xy is not None:
        lx, ly = last_xy
        best = min(candidates, key=lambda t: (t[0] - lx) ** 2 + (t[1] - ly) ** 2)
        best_cx, best_cy, best_area, best_contour = best
    elif selection_mode == "closest_else_largest" and last_xy is not None:
        lx, ly = last_xy
        best = min(candidates, key=lambda t: (t[0] - lx) ** 2 + (t[1] - ly) ** 2)
        best_cx, best_cy, best_area, best_contour = best
        if max_jump_px > 0:
            d = ((best_cx - lx) ** 2 + (best_cy - ly) ** 2) ** 0.5
            if d > max_jump_px:
                best = max(candidates, key=lambda t: t[2])
                best_cx, best_cy, best_area, best_contour = best
    else:
        best = max(candidates, key=lambda t: t[2])
        best_cx, best_cy, best_area, best_contour = best
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
    ):
        self.sleap_model_paths = sleap_model_paths or []
        self.confidence_threshold = confidence_threshold
        self.min_nodes_required = max(1, min_nodes_required)
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

                # Pass empty preprocess_config so sleap-nn never sees None
                # (avoids 'NoneType' has no attribute 'items')
                from omegaconf import OmegaConf

                predictor = SingleInstancePredictor.from_trained_models(
                    confmap_ckpt_path=str(path),
                    device=device,
                    batch_size=1,
                    preprocess_config=OmegaConf.create({}),
                )

                self._sleap_predictor = predictor
                actual = next(predictor.confmap_model.parameters()).device
                self._sleap_device = str(actual)
                _LOG.info("SLEAP: model loaded on %s", actual)
                self._sleap_status = "ok"
                self._sleap_status_error = None
                return True
            except Exception as e:
                self._sleap_status = "load_failed"
                import traceback

                self._sleap_last_fail_s = time.monotonic()
                # Include traceback so Help -> View error log has the real origin.
                self._sleap_status_error = (
                    f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
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
            # (1, C, H, W)
            def ensure_4d(t: "torch.Tensor") -> "torch.Tensor":
                if t.dim() == 3:
                    return t.unsqueeze(0)
                return t

            img = _numpy_to_tensor_batch(image).to(device)
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

    def track(self, image: np.ndarray) -> TrackingResult:
        # Always compute fallback so "in-range" can be recorded continuously.
        fallback_res = self._fallback.track(image)
        if self._ensure_sleap() and self._sleap_predictor is not None:
            res = self._predict_frame_sleap(image)
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
                    fallback_res = self._fallback.track(image)
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
                )
            _LOG.debug("SLEAP: _predict_frame_sleap returned None, using fallback")
        else:
            _LOG.debug("SLEAP: not available (_ensure_sleap=False or no predictor), using fallback")
        return fallback_res


# -----------------------------------------------------------------------------
# TrackingController: GUI orchestration (tracker cache, async worker, run-every-N)
# -----------------------------------------------------------------------------

_TRACKING_STALE_S = 0.132  # ~2× 33 ms; matches GUI constant


def _build_or_refresh_tracker(
    config: ControllerConfig,
    cached_key: Optional[tuple],
    cached_tracker: Optional[object],
    *,
    sleap_path: str,
    backup_only: bool,
) -> Tuple[object, tuple]:
    """
    Build or refresh the tracker used for real-time tracking.

    This mirrors the tracker construction logic currently implemented in
    `MainWindow._on_camera_tick`, but is factored out here so that
    `TrackingController` can own the tracker lifecycle.

    Parameters
    ----------
    config:
        The current controller configuration (includes fallback tracking settings
        and SLEAP confidence / run-every-N parameters).
    cached_key:
        The last tracker key used to build `cached_tracker`, or None.
    cached_tracker:
        The previously built tracker instance, or None.
    sleap_path:
        Path to the SLEAP model directory. Empty string means "no SLEAP",
        in which case only the fallback tracker is used.
    backup_only:
        If True, ignore `sleap_path` and always use the fallback tracker only.

    Returns
    -------
    tracker:
        The tracker instance to use (HybridTracker or AdaptiveThresholdTracker).
    key:
        The key tuple that uniquely identifies the tracker configuration.
    """
    if backup_only:
        sleap_path = ""

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
        sleap_path,
        backup_only,
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

    if sleap_path and HybridTracker is not None:
        tracker = HybridTracker(
            sleap_model_paths=[sleap_path],
            confidence_threshold=confidence_pct,
            fallback_tracker=fallback,
            min_nodes_required=min_sleap_nodes,
        )
    else:
        tracker = fallback

    return tracker, key


def _tracking_worker_loop(
    q: queue.Queue,
    lock: threading.Lock,
    result_holder: list,
    result_time_holder: list,
    running_holder: list,
) -> None:
    """
    Background thread: get (frame, tracker) from queue, run track(), store result and timestamp.

    This is adapted from the `_tracking_worker_loop` implementation in
    `vast_controller.gui.main_window`, but is defined here so that it can be
    owned and managed by `TrackingController`.
    """
    while running_holder[0]:
        try:
            item = q.get(timeout=0.05)
        except queue.Empty:
            continue
        if item is None:
            break
        frame, tracker = item
        if frame is None or tracker is None:
            continue
        try:
            res = tracker.track(frame)
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
    - Own a cached tracker (HybridTracker + AdaptiveThresholdTracker) based on `ControllerConfig`
      and the current SLEAP model path / backup-only settings.
    - Optionally run tracking in an async worker thread and queue when async is enabled.
    - Implement run-every-N SLEAP logic using `config.sleap_every_n`.
    - Expose a small API that `MainWindow` can use from camera callbacks.
    """

    def __init__(self, config: ControllerConfig) -> None:
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

        # GUI-owned parameters that are not in ControllerConfig yet; these will be
        # set by the GUI when wiring happens in later refactor steps.
        self._sleap_path: str = ""
        self._backup_only: bool = False

    # Internal helpers -----------------------------------------------------------

    def _ensure_tracker(self) -> object:
        """Build or refresh the cached tracker and return it."""
        tracker, key = _build_or_refresh_tracker(
            self._config,
            self._cached_tracker_key,
            self._cached_tracker,
            sleap_path=self._sleap_path,
            backup_only=self._backup_only,
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

    def set_sleap_params(self, sleap_path: str, backup_only: bool) -> None:
        """
        Update SLEAP model path and backup-only flag, invalidating tracker cache.

        This is typically called from the GUI when the SLEAP path text field or
        "Backup tracking only" checkbox changes.

        If called every frame with the same values (e.g. from the camera tick),
        this must be a no-op: clearing the cache every frame rebuilds HybridTracker
        and reloads the SLEAP model, destroying display FPS (~6–7 instead of 30+).
        """
        path = sleap_path.strip()
        backup = bool(backup_only)
        if path == self._sleap_path and backup == self._backup_only:
            return
        self._sleap_path = path
        self._backup_only = backup
        self._cached_tracker_key = None
        self._last_tracking_result = None
        self._track_frame_counter = 0

    def set_config(self, config: ControllerConfig) -> None:
        """
        Replace the current `ControllerConfig` and invalidate cached trackers.

        This should be called after settings or profile changes so that the
        next frame submission rebuilds the tracker with updated parameters.
        """
        self._config = config
        self._cached_tracker_key = None
        self._last_tracking_result = None
        self._track_frame_counter = 0

    def submit_frame(self, image: np.ndarray, now_s: float) -> None:
        """
        Submit a frame for tracking.

        Parameters
        ----------
        image:
            The current camera frame as a numpy array. For consistency with the
            existing implementation, this should be the *raw* frame before any
            display-only brightness/contrast adjustments.
        now_s:
            Timestamp (e.g. `time.monotonic()`) corresponding to this frame.

        In async mode, this enqueues the frame for the worker thread.
        In sync mode, this performs tracking immediately (respecting
        `config.sleap_every_n`) and stores the resulting `TrackingResult`.
        """
        tracker = self._ensure_tracker()

        if self._async_enabled:
            queue_was_full = False
            try:
                # Worker owns the copy so the caller can safely reuse its array.
                self._queue.put_nowait((image.copy(), tracker))
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
            res = tracker.track(image)
            self._last_tracking_result = res
        else:
            res = self._last_tracking_result

        self._track_frame_counter += 1

        with self._lock:
            self._result_holder[0] = res
            self._result_time_holder[0] = now_s

    def get_latest_result(self) -> Optional[TrackingResult]:
        """
        Return the most recent `TrackingResult`, if any.

        For async mode, this returns the last result produced by the worker
        thread. For sync mode, this returns the result computed from the most
        recent call to `submit_frame`.
        """
        with self._lock:
            res = self._result_holder[0]
        return res

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
        app_logging.log_error("SLEAP: " + err_str)
        return "failed", "SLEAP model load status. Error: " + err_str
