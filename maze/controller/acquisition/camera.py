"""
Camera capture: live frame stream for Manta G201B (Vimba) or fallback OpenCV.

Target: ~30 fps, standard def. Frame buffer with timestamps for sync with H5/video.
Also provides the camera controller (lifecycle, frame acquisition) and display/click helpers.
"""

from __future__ import annotations

import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

from . import app_logging
from .shared_config import AcquisitionConfig

import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import vmbpy
    HAS_VIMBA = True
except ImportError:
    vmbpy = None
    HAS_VIMBA = False

HAS_CAMERA = HAS_CV2 or HAS_VIMBA


@dataclass
class Frame:
    """Single frame with timestamp."""
    image: np.ndarray  # (H, W) or (H, W, C), dtype uint8
    timestamp: float   # monotonic time from start
    frame_index: int


def effective_frame_count_for_virtual_timing(
    file_total_frames: Optional[int],
    anchor_frame_index: Optional[int],
) -> Optional[int]:
    """
    Frame count paired with ``virtual_duration_override_s`` to compute **constant** effective FPS.

    ``anchor_frame_index`` is the 0-based start of the pacing segment (inclusive), fixed until
    the next seek: ``max(1, file_total_frames - clamp(anchor, 0, total))``. The override
    duration is spread evenly over that many frames, so playback and per-frame virtual time
    stay linear. Passing ``None`` or negative anchor uses ``0`` (whole file).

    :meth:`CameraController` sets the anchor on virtual open (0) and on each successful
    :meth:`seek_video_frame`.
    """
    if file_total_frames is None:
        return None
    t = int(file_total_frames)
    if t <= 0:
        return None
    if anchor_frame_index is None or int(anchor_frame_index) < 0:
        a = 0
    else:
        a = min(max(0, int(anchor_frame_index)), t)
    return max(1, t - a)


class BaseCamera(ABC):
    """Abstract camera interface."""

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def read(self) -> Optional[Frame]:
        """Return latest frame or None if not available."""
        pass

    @property
    @abstractmethod
    def fps(self) -> float:
        pass

    @property
    @abstractmethod
    def shape(self) -> tuple:
        """(height, width) or (height, width, channels)."""
        pass

    # Optional: total frame count if known (used for UI indicators).
    def total_frames(self) -> Optional[int]:
        return None


class OpenCVCamera(BaseCamera):
    """
    OpenCV VideoCapture (e.g. USB webcam or generic GigE).
    For Manta G201B use vendor SDK if available; otherwise try cv2 with device index.
    """

    def __init__(
        self,
        device: int = 0,
        width: Optional[int] = 640,
        height: Optional[int] = 480,
        fps_target: float = 30.0,
    ):
        if not HAS_CV2:
            raise RuntimeError("opencv-python is required for OpenCVCamera")
        self._device = device
        self._width = width
        self._height = height
        self._fps_target = fps_target
        self._cap: Optional[cv2.VideoCapture] = None
        self._start_time = 0.0
        self._frame_index = 0

    def start(self) -> None:
        # On Windows use DirectShow to avoid FFmpeg/obsensor probe and to target GigE (e.g. Manta).
        if sys.platform == "win32":
            self._cap = cv2.VideoCapture(self._device, cv2.CAP_DSHOW)
        else:
            self._cap = cv2.VideoCapture(self._device)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open camera device {self._device}")
        if self._width is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        if self._height is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap.set(cv2.CAP_PROP_FPS, self._fps_target)
        try:
            total = self._cap.get(cv2.CAP_PROP_FRAME_COUNT)
            self._total_frames = int(total) if total and total > 0 else None
        except Exception:
            self._total_frames = None
        self._start_time = time.monotonic()
        self._frame_index = 0

    def total_frames(self) -> Optional[int]:
        return getattr(self, "_total_frames", None)

    def stop(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def read(self) -> Optional[Frame]:
        if self._cap is None or not self._cap.isOpened():
            return None
        ok, img = self._cap.read()
        if not ok or img is None:
            return None
        ts = time.monotonic() - self._start_time
        idx = self._frame_index
        self._frame_index += 1
        return Frame(image=img, timestamp=ts, frame_index=idx)

    @property
    def fps(self) -> float:
        if self._cap is None:
            return self._fps_target
        f = self._cap.get(cv2.CAP_PROP_FPS)
        return float(f) if f > 0 else self._fps_target

    @property
    def shape(self) -> tuple:
        if self._cap is None:
            return (self._height or 480, self._width or 640, 3)
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        return (h, w, 3)

    def __enter__(self) -> "OpenCVCamera":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()


class VideoFileCamera(BaseCamera):
    """Read frames from a video file and present them through the BaseCamera API."""

    def __init__(self, video_path: Path | str, fps_target: float = 30.0, loop: bool = True):
        if not HAS_CV2:
            raise RuntimeError("opencv-python is required for VideoFileCamera")
        self._video_path = str(video_path)
        self._fps_target = float(fps_target)
        self._loop = bool(loop)
        self._cap: Optional["cv2.VideoCapture"] = None
        self._start_time = 0.0
        self._frame_index = 0
        self._shape: tuple = (480, 640, 3)
        self._total_frames: Optional[int] = None

    def start(self) -> None:
        self._cap = cv2.VideoCapture(self._video_path)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open video file: {self._video_path}")
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        self._shape = (h, w, 3)
        try:
            total = self._cap.get(cv2.CAP_PROP_FRAME_COUNT)
            self._total_frames = int(total) if total and total > 0 else None
        except Exception:
            self._total_frames = None
        self._start_time = time.monotonic()
        self._frame_index = 0

    def total_frames(self) -> Optional[int]:
        return self._total_frames

    def seek_to_start(self) -> None:
        """Rewind to the beginning of the video file."""
        self.seek_to_frame(0)

    def seek_to_frame(self, index: int) -> bool:
        """Seek to a 0-based frame index (best-effort; accuracy depends on codec/container)."""
        if self._cap is None or not self._cap.isOpened():
            return False
        idx = max(0, int(index))
        try:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, float(idx))
        except Exception:
            return False
        self._start_time = time.monotonic()
        try:
            pos = self._cap.get(cv2.CAP_PROP_POS_FRAMES)
            self._frame_index = int(pos) if pos is not None and pos >= 0 else idx
        except Exception:
            self._frame_index = idx
        return True

    def stop(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
        self._cap = None

    def read(self) -> Optional[Frame]:
        if self._cap is None or not self._cap.isOpened():
            return None
        ok, img = self._cap.read()
        if not ok or img is None:
            if self._loop:
                # Seek back to first frame and retry once.
                try:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, img = self._cap.read()
                except Exception:
                    ok = False
            if not ok or img is None:
                return None
        ts = time.monotonic() - self._start_time
        idx = self._frame_index
        self._frame_index += 1
        return Frame(image=img, timestamp=ts, frame_index=idx)

    @property
    def fps(self) -> float:
        if self._cap is None:
            return self._fps_target
        f = float(self._cap.get(cv2.CAP_PROP_FPS))
        return f if f > 0 else self._fps_target

    @property
    def shape(self) -> tuple:
        return self._shape

    def __enter__(self) -> "VideoFileCamera":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()


class VimbaCamera(BaseCamera):
    """
    Allied Vision GigE/USB camera via Vimba (vmbpy), e.g. Manta G201B.
    Requires Vimba X SDK and vmbpy (pip install vmbpy or use the wheel from the SDK).
    Does not change camera features on connect; use get_current_settings() to read config.
    """

    def __init__(self, device_index: int = 0, fps_target: float = 30.0):
        if not HAS_VIMBA or vmbpy is None:
            raise RuntimeError("vmbpy (Vimba) is required for VimbaCamera")
        self._device_index = device_index
        self._fps_target = fps_target
        self._vmb: Any = None
        self._cam: Any = None
        self._start_time = 0.0
        self._frame_index = 0
        self._shape: tuple = (480, 640, 3)
        self._current_settings: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._latest_img: Optional[np.ndarray] = None
        self._latest_frame_index = 0

    def _frame_handler(self, cam: Any, _stream: Any, frame: Any) -> None:
        try:
            try:
                img = frame.as_opencv_image()
            except Exception:
                img = frame.as_numpy_ndarray()
            if img is not None:
                img = np.asarray(img).copy()
                with self._lock:
                    self._latest_img = img
                    self._latest_frame_index = self._frame_index
                    self._frame_index += 1
                    self._shape = img.shape if img.ndim == 3 else (img.shape[0], img.shape[1], 1)
        except Exception:
            pass
        try:
            cam.queue_frame(frame)
        except Exception:
            pass

    def get_current_settings(self) -> dict[str, Any]:
        """
        Read current camera settings (pixel format, width, height, etc.).
        Call after start(). Returns dict with pixel_format, width, height, decimation_*.
        """
        out: dict[str, Any] = {
            "pixel_format": None,
            "width": None,
            "height": None,
            "decimation_horizontal": None,
            "decimation_vertical": None,
        }
        if self._cam is None:
            return out
        try:
            out["pixel_format"] = str(self._cam.get_pixel_format())
        except Exception:
            pass
        try:
            w = self._cam.get_feature_by_name("Width")
            if w is not None:
                out["width"] = int(w.get())
        except Exception:
            pass
        try:
            h = self._cam.get_feature_by_name("Height")
            if h is not None:
                out["height"] = int(h.get())
        except Exception:
            pass
        for key, feat in (("decimation_horizontal", "DecimationHorizontal"), ("decimation_vertical", "DecimationVertical")):
            try:
                f = self._cam.get_feature_by_name(feat)
                if f is not None:
                    out[key] = int(f.get())
            except Exception:
                pass
        self._current_settings = out
        return out

    def start(self) -> None:
        if not HAS_VIMBA or vmbpy is None:
            raise RuntimeError("vmbpy (Vimba) is required")
        self._vmb = vmbpy.VmbSystem.get_instance()
        self._vmb.__enter__()
        cams = self._vmb.get_all_cameras()
        if not cams:
            self._vmb.__exit__(None, None, None)
            self._vmb = None
            raise RuntimeError("No Vimba cameras found; check connection and Vimba X installation.")
        if self._device_index >= len(cams):
            self._vmb.__exit__(None, None, None)
            self._vmb = None
            raise RuntimeError(f"Camera index {self._device_index} out of range (found {len(cams)}).")
        self._cam = cams[self._device_index]
        self._cam.__enter__()
        try:
            self._cam.GVSPAdjustPacketSize.run()
            while not self._cam.GVSPAdjustPacketSize.is_done():
                pass
        except (AttributeError, Exception):
            pass
        self._cam.start_streaming(
            handler=self._frame_handler,
            buffer_count=10,
        )
        self.get_current_settings()
        self._start_time = time.monotonic()
        self._frame_index = 0
        with self._lock:
            self._latest_img = None
            self._latest_frame_index = 0

    def stop(self) -> None:
        if self._cam is not None:
            try:
                self._cam.stop_streaming()
            except Exception:
                pass
            try:
                self._cam.__exit__(None, None, None)
            except Exception:
                pass
            self._cam = None
        if self._vmb is not None:
            try:
                self._vmb.__exit__(None, None, None)
            except Exception:
                pass
            self._vmb = None
        with self._lock:
            self._latest_img = None

    def read(self) -> Optional[Frame]:
        with self._lock:
            img = self._latest_img
            idx = self._latest_frame_index
        if img is None:
            return None
        ts = time.monotonic() - self._start_time
        return Frame(image=img.copy(), timestamp=ts, frame_index=idx)

    @property
    def fps(self) -> float:
        return self._fps_target

    @property
    def shape(self) -> tuple:
        return self._shape

    def __enter__(self) -> "VimbaCamera":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()


def apply_display_adjustments(
    img: np.ndarray,
    brightness: int,
    contrast_pct: int,
) -> np.ndarray:
    """
    Apply display-only brightness (offset) and contrast (scale).

    - ``brightness``: -100..100 (added after contrast).
    - ``contrast_pct``: 50..200 (100 = no change; scale around 128).
    """
    if not HAS_CV2 or (brightness == 0 and contrast_pct == 100):
        return img
    # Calculate scale factor and offset, applying always in uint8
    scale = contrast_pct / 100.0
    offset = float(brightness)
    # Apply contrast and brightness while staying in uint8 domain
    # Using cv2.addWeighted for uint8 image math
    # (out - 128) * scale + 128 + brightness == out * scale + 128*(1-scale) + brightness
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    out = cv2.addWeighted(img, scale, img, 0, 128 * (1.0 - scale) + offset)
    return out


def map_click_to_image_coords(
    lx: float,
    ly: float,
    label_width: int,
    label_height: int,
    img_width: int,
    img_height: int,
) -> Tuple[int, int]:
    """
    Map label-space click coordinates to image-space coordinates.

    This reproduces the mapping used in `MainWindow.eventFilter`, where the
    image is scaled to fit inside the preview label while preserving aspect
    ratio (letterboxing as needed).
    """
    if img_width <= 0 or img_height <= 0:
        return 0, 0

    scale = min(label_width / img_width, label_height / img_height)
    pw, ph = int(img_width * scale), int(img_height * scale)
    ox, oy = (label_width - pw) // 2, (label_height - ph) // 2
    ix = int((lx - ox) / scale)
    iy = int((ly - oy) / scale)
    ix = max(0, min(img_width - 1, ix))
    iy = max(0, min(img_height - 1, iy))
    return ix, iy


class CameraController:
    """
    Owns camera open/close and frame acquisition.

    The controller is UI-agnostic: it does not depend on Qt widgets. The GUI
    should:
    - Construct it with an `AcquisitionConfig`.
    - Call `open` / `close`.
    - On each timer tick, call `grab_frame()` and then apply any display-only
      adjustments or overlays for preview.
    """

    def __init__(self, config: AcquisitionConfig) -> None:
        self._config = config
        self._camera: Optional[object] = None
        self._last_preview_img_size: Optional[Tuple[int, int]] = None
        self._last_frame_index: Optional[int] = None
        self._last_total_frames: Optional[int] = None
        #: 0-based start frame for ``virtual_duration_override`` pacing (virtual file only).
        self._virtual_override_anchor_frame: Optional[int] = None

    def open(self, source: str, device_index: int, video_path: Optional[Path] = None) -> None:
        """
        Open the camera for the given source and device index.

        Parameters
        ----------
        source:
            String label such as "OpenCV" or "GigE (Vimba)".
        device_index:
            Integer device index for the backend.
        video_path:
            Required when source == "Virtual (video file)".
        """
        if not HAS_CAMERA:
            app_logging.log_error("CameraController: camera backend unavailable.")
            return

        # Always close any existing camera before opening a new one.
        self.close()

        use_virtual = source.startswith("Virtual")
        use_gige = source.startswith("GigE") and HAS_VIMBA and VimbaCamera is not None
        try:
            if use_virtual:
                if video_path is None:
                    raise ValueError("video_path is required for Virtual (video file) source")
                self._camera = VideoFileCamera(video_path=video_path, fps_target=30.0, loop=True)
                self._camera.start()
                self._virtual_override_anchor_frame = 0
            elif use_gige:
                self._camera = VimbaCamera(
                    device_index=device_index,
                    fps_target=30.0,
                )
                self._camera.start()
            else:
                if OpenCVCamera is None:
                    app_logging.log_error("CameraController: OpenCVCamera backend unavailable.")
                    return
                self._camera = OpenCVCamera(
                    device=device_index,
                    width=640,
                    height=480,
                    fps_target=30.0,
                )
                self._camera.start()
        except Exception as e:  # pragma: no cover - defensive logging
            app_logging.log_error(f"CameraController: failed to open camera: {e}")
            if self._camera is not None:
                try:
                    self._camera.stop()
                except Exception:
                    pass
                self._camera = None

    def close(self) -> None:
        """Stop and release the underlying camera, if any."""
        cam = self._camera
        self._camera = None
        if cam is not None:
            try:
                cam.stop()
            except Exception:  # pragma: no cover - defensive logging
                app_logging.log_error("CameraController: error while stopping camera.")
        self._last_preview_img_size = None
        self._virtual_override_anchor_frame = None

    def grab_frame(self) -> Optional[np.ndarray]:
        """
        Read a frame from the underlying camera.

        Returns
        -------
        frame:
            Numpy array of shape (H, W) or (H, W, C), or None if no frame is
            available or no camera is open.
        """
        if self._camera is None:
            return None
        try:
            frame = self._camera.read()
        except Exception as e:  # pragma: no cover - defensive logging
            app_logging.log_error(f"CameraController: read() failed: {e}")
            return None
        if frame is None or getattr(frame, "image", None) is None:
            return None
        img = frame.image
        self._last_frame_index = int(getattr(frame, "frame_index", -1)) if frame is not None else None
        try:
            self._last_total_frames = self._camera.total_frames() if hasattr(self._camera, "total_frames") else None
        except Exception:
            self._last_total_frames = None
        if isinstance(img, np.ndarray):
            h, w = img.shape[0], img.shape[1]
            self._last_preview_img_size = (w, h)
        return img

    def get_last_frame_info(self) -> Tuple[Optional[int], Optional[int]]:
        """Return (current_frame_index_0based, total_frames) if known."""
        return (self._last_frame_index, self._last_total_frames)

    def rewind(self) -> None:
        """Rewind the underlying camera if it supports seeking (virtual mode)."""
        self.seek_video_frame(0)

    def seek_video_frame(self, index: int) -> bool:
        """Seek file-backed video to ``index``; no-op for live cameras. Returns whether seek was attempted."""
        cam = self._camera
        if cam is None:
            return False
        fn = getattr(cam, "seek_to_frame", None)
        if not callable(fn):
            return False
        ok = bool(fn(int(index)))
        if ok:
            idx = int(index)
            self._last_frame_index = idx
            self._virtual_override_anchor_frame = idx
        return ok

    def get_last_preview_size(self) -> Optional[Tuple[int, int]]:
        """Return the last preview image size as (width, height), if known."""
        return self._last_preview_img_size

    def virtual_file_nominal_fps(self) -> Optional[float]:
        """
        Nominal frames-per-second from virtual file metadata (``CAP_PROP_FPS``),
        if the active backend is file-based. Used for preview timer pacing and
        trial recording metadata. Returns ``None`` for live cameras.
        """
        cam = self._camera
        if cam is None or not isinstance(cam, VideoFileCamera):
            return None
        fps = float(cam.fps)
        if fps <= 0:
            return None
        # Guard absurd container values so the Qt timer stays reasonable.
        return float(max(1.0, min(fps, 360.0)))

    def virtual_file_effective_fps(self, config: Optional[AcquisitionConfig] = None) -> Optional[float]:
        """
        Effective virtual FPS for GUI pacing/recording.

        If ``config.virtual_duration_override_s`` is set (>0) and total frame count
        is known, compute FPS as ``timing_frames / duration_override_s``, where
        ``timing_frames`` is fixed for the segment from the **anchor** frame (0 on open,
        updated on each :meth:`seek_video_frame`) to EOF — constant effective FPS until
        the next seek. Otherwise fall back to container nominal FPS.
        """
        nominal = self.virtual_file_nominal_fps()
        cam = self._camera
        if cam is None or not isinstance(cam, VideoFileCamera):
            return None
        if config is None:
            return nominal
        try:
            dur = getattr(config, "virtual_duration_override_s", None)
            if dur is None:
                return nominal
            dur_s = float(dur)
            if dur_s <= 0:
                return nominal
            total = cam.total_frames()
            anchor = self._virtual_override_anchor_frame
            if anchor is None:
                anchor = 0
            timing_frames = effective_frame_count_for_virtual_timing(total, anchor)
            if timing_frames is None:
                return nominal
            fps_eff = float(timing_frames) / dur_s
            if fps_eff <= 0:
                return nominal
            return float(max(1.0, min(fps_eff, 360.0)))
        except Exception:
            return nominal

    def virtual_file_timing_info(
        self, config: Optional[AcquisitionConfig] = None
    ) -> Optional[dict[str, Optional[float]]]:
        """
        Return timing diagnostics for virtual sources, or ``None`` for live cameras.
        """
        cam = self._camera
        if cam is None or not isinstance(cam, VideoFileCamera):
            return None
        nominal = self.virtual_file_nominal_fps()
        effective = self.virtual_file_effective_fps(config)
        total = cam.total_frames()
        anchor = self._virtual_override_anchor_frame
        if anchor is None:
            anchor = 0
        timing_frames = effective_frame_count_for_virtual_timing(total, anchor)
        override_s = None
        if config is not None:
            try:
                v = getattr(config, "virtual_duration_override_s", None)
                override_s = float(v) if v is not None else None
            except Exception:
                override_s = None
        return {
            "nominal_fps": nominal,
            "effective_fps": effective,
            "total_frames": float(total) if total is not None else None,
            "total_frames_for_effective_fps": (
                float(timing_frames) if timing_frames is not None else None
            ),
            "virtual_override_anchor_frame": float(anchor),
            "duration_override_s": override_s,
        }

    def preview_timer_interval_ms(self, config: Optional[AcquisitionConfig] = None) -> int:
        """
        Milliseconds between GUI preview ticks.

        Virtual (video file) uses the file's nominal FPS so playback matches
        the container's reported sampling rate. Live sources keep ~30 Hz.
        """
        fps = self.virtual_file_effective_fps(config)
        if fps is not None:
            return max(1, int(round(1000.0 / fps)))
        return 33
