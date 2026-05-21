"""Camera preview label event filter (eyedropper hover, center/range pick from click)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent

from ..camera import map_click_to_image_coords
from .intensity_sample import (
    fallback_range_from_gray_patch,
    gray_neighborhood_patch_bgr,
    gray_value_at_pixel_bgr,
)

if TYPE_CHECKING:
    from .main_window import MainWindow


def filter_camera_preview_events(window: MainWindow, obj: object, event: QEvent) -> None:
    """
    Handle mouse events on ``window._camera_label`` (``installEventFilter`` target).

    Does not consume events; ``MainWindow.eventFilter`` always delegates to ``super()``.
    """
    if obj is not window._camera_label:
        return
    if event.type() == QEvent.Type.MouseMove:
        if (
            window._camera_timer is not None
            and window._camera_timer.isActive()
            and window._camera_controller is not None
            and window._last_eyedropper_frame_bgr is not None
        ):
            size = window._camera_controller.get_last_preview_size()
            if size is not None:
                iw, ih = size
                if iw > 0 and ih > 0:
                    lw, lh = window._camera_label.width(), window._camera_label.height()
                    lx, ly = event.position().x(), event.position().y()
                    ix, iy = map_click_to_image_coords(
                        lx,
                        ly,
                        lw,
                        lh,
                        iw,
                        ih,
                    )
                    gv = gray_value_at_pixel_bgr(
                        window._last_eyedropper_frame_bgr, int(ix), int(iy)
                    )
                    if gv is not None:
                        window._intensity_hover_label.setText(str(gv))
        return
    if event.type() == QEvent.Type.MouseButtonPress:
        if (
            bool(getattr(window._config, "preview_set_center_from_next_click", False))
            and window._camera_controller is not None
        ):
            size = window._camera_controller.get_last_preview_size()
            if size is not None:
                iw, ih = size
                if iw > 0 and ih > 0:
                    lw, lh = window._camera_label.width(), window._camera_label.height()
                    lx, ly = event.position().x(), event.position().y()
                    ix, iy = map_click_to_image_coords(
                        lx,
                        ly,
                        lw,
                        lh,
                        iw,
                        ih,
                    )
                    if window._task_mode == "ram" and hasattr(window._config, "radial_arm"):
                        window._config.radial_arm.calibration.template_center_x_px = float(ix)
                        window._config.radial_arm.calibration.template_center_y_px = float(iy)
                        message = f"RAM template center set to ({ix}, {iy})"
                    else:
                        window._config.arena.arena_center_x_px = float(ix)
                        window._config.arena.arena_center_y_px = float(iy)
                        message = f"Arena center set to ({ix}, {iy})"
                    window._config.preview_set_center_from_next_click = False
                    window.statusBar().showMessage(message)
                    dlg = getattr(window, "_settings_dialog", None)
                    if dlg is not None and hasattr(
                        dlg, "sync_preview_center_checkbox_from_config"
                    ):
                        dlg.sync_preview_center_checkbox_from_config()
                    if (
                        window._task_mode == "ram"
                        and dlg is not None
                        and hasattr(dlg, "sync_ram_template_center_widgets")
                    ):
                        dlg.sync_ram_template_center_widgets()
        elif (
            bool(getattr(window._config.fallback_tracking, "range_from_next_click", False))
            and window._camera_controller is not None
        ):
            size = window._camera_controller.get_last_preview_size()
            frm = window._last_eyedropper_frame_bgr
            if size is not None and frm is not None:
                iw, ih = size
                if iw > 0 and ih > 0:
                    lw, lh = window._camera_label.width(), window._camera_label.height()
                    lx, ly = event.position().x(), event.position().y()
                    ix, iy = map_click_to_image_coords(
                        lx,
                        ly,
                        lw,
                        lh,
                        iw,
                        ih,
                    )
                    ft = window._config.fallback_tracking
                    half = max(0, int(getattr(ft, "range_pick_half", 2)))
                    delta = max(0, int(getattr(ft, "range_pick_delta", 12)))
                    patch = gray_neighborhood_patch_bgr(frm, int(ix), int(iy), half)
                    if patch is not None:
                        lo, hi = fallback_range_from_gray_patch(patch, delta)
                        window._config.fallback_tracking.range_low = lo
                        window._config.fallback_tracking.range_high = hi
                        window.statusBar().showMessage(
                            f"Backup intensity range set to [{lo}, {hi}] (neighborhood ±{delta})."
                        )
                    else:
                        window.statusBar().showMessage(
                            "Could not sample neighborhood for range."
                        )
                    window._config.fallback_tracking.range_from_next_click = False
                    dlg = getattr(window, "_settings_dialog", None)
                    if dlg is not None and hasattr(
                        dlg, "sync_fallback_intensity_range_widgets"
                    ):
                        dlg.sync_fallback_intensity_range_widgets()
